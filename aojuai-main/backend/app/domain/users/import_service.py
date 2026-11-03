"""从 CSV 批量导入用户。

为什么需要它：一个试点小组十几二十号人，在后台一个个建、再一个个分配团队和角色，
不但慢，而且**中间出错很难看出来**——漏了一个人的团队分配，那个人登录后什么都
做不了，还得等他自己反馈。

三条设计原则：

1. **先预演、再执行。** 导入是很难撤销的操作。`dry_run=True` 走完全部校验、
   给出逐行结论，但一行都不写库。前端必须先预演、把结果给人看过，再提交执行。
2. **逐行独立。** 一行有问题不该让整个文件失败——那会逼人把 200 行的表格
   反复试错。错误行报出来，其余照常导入。
3. **可重复执行。** 同一份 CSV 跑第二遍不该产生重复用户。已存在的按 `skipped`
   计，不是报错——重跑一遍补上次失败的几行，是最自然的用法。

**团队和角色用名字/编码填，不用 ID。** 让人去后台查数字 ID 再填进表格，
是把系统的内部表示当成用户的工作量，多数错误就来自这里。
"""

from __future__ import annotations

import csv
import io
import re
import secrets
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.domain.roles.models import Role
from app.domain.teams.models import Team
from app.domain.users.models import User
from app.domain.users.schemas import UserCreate
from app.domain.users.service import UserService

logger = get_logger(__name__)

#: CSV 表头。中英文都认——给业务同事的模板用中文，给脚本用英文。
COLUMN_ALIASES: dict[str, str] = {
    "username": "username", "账号": "username", "用户名": "username", "登录名": "username",
    "nickname": "nickname", "姓名": "nickname", "昵称": "nickname",
    "phone": "phone", "手机": "phone", "手机号": "phone",
    "email": "email", "邮箱": "email",
    "team": "team", "团队": "team", "小组": "team", "部门": "team",
    "role": "role", "角色": "role",
    "password": "password", "初始密码": "password",
    "remark": "remark", "备注": "remark",
}

REQUIRED_COLUMNS = ("username",)

MAX_ROWS = 1000

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{2,50}$")


@dataclass
class RowOutcome:
    line: int
    username: str
    #: created | skipped | error
    status: str
    message: str = ""
    #: 仅新建用户时返回，且**只返回这一次**
    initial_password: str | None = None
    resolved_team: str | None = None
    resolved_role: str | None = None


@dataclass
class ImportOutcome:
    dry_run: bool
    total: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    rows: list[RowOutcome] = field(default_factory=list)
    #: 表头层面的问题（缺列、认不出的列），这类问题整份文件都没法处理
    header_errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "dryRun": self.dry_run,
            "total": self.total,
            "created": self.created,
            "skipped": self.skipped,
            "failed": self.failed,
        }


def _normalize_header(name: str) -> str | None:
    key = str(name or "").strip().lstrip("﻿").lower()
    return COLUMN_ALIASES.get(key)


def parse_csv(content: str) -> tuple[list[dict[str, str]], list[str]]:
    """解析 CSV，返回 (规范化后的行, 表头错误)。

    表头认中英文别名；认不出的列直接忽略而不是报错——业务同事的表格里常有
    "序号""入职日期"这类跟导入无关的列，为它们报错只会让人困惑。
    """
    errors: list[str] = []
    text = str(content or "").lstrip("﻿")
    if not text.strip():
        return [], ["文件是空的"]

    reader = csv.reader(io.StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        return [], ["文件是空的"]

    mapping: dict[int, str] = {}
    for index, name in enumerate(raw_header):
        canonical = _normalize_header(name)
        if canonical:
            mapping[index] = canonical

    missing = [col for col in REQUIRED_COLUMNS if col not in mapping.values()]
    if missing:
        errors.append(
            f"缺少必需的列：{'、'.join(missing)}。"
            f"表头可用中文或英文，例如：账号,姓名,手机,团队,角色"
        )
        return [], errors

    rows: list[dict[str, str]] = []
    for line_number, raw in enumerate(reader, start=2):
        if not any(str(cell).strip() for cell in raw):
            continue  # 空行：表格末尾常见，跳过而不是报错
        row = {"__line__": str(line_number)}
        for index, canonical in mapping.items():
            if index < len(raw):
                row[canonical] = str(raw[index]).strip()
        rows.append(row)
        if len(rows) > MAX_ROWS:
            errors.append(f"一次最多导入 {MAX_ROWS} 行，请拆分文件")
            return [], errors
    return rows, errors


def generate_initial_password() -> str:
    """生成初始密码。

    **不接受 CSV 里填明文密码**：那份文件会躺在邮箱、聊天记录和下载目录里。
    这里生成随机密码，只在导入结果里返回一次，由管理员线下转交。
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    body = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"Aoju@{body}"


class UserImportService:
    def __init__(self, db: AsyncSession, *, tenant_id: int, actor_id: int | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self._teams: dict[str, int] | None = None
        self._roles: dict[str, int] | None = None

    async def _team_index(self) -> dict[str, int]:
        """团队按 name 和 code 都建索引，两种写法都能对上。"""
        if self._teams is None:
            rows = await self.db.execute(
                select(Team.id, Team.name, Team.code).where(
                    Team.tenant_id == self.tenant_id, Team.deleted_at.is_(None)
                )
            )
            index: dict[str, int] = {}
            for team_id, name, code in rows.all():
                for key in (name, code):
                    if key:
                        index[str(key).strip().lower()] = int(team_id)
            self._teams = index
        return self._teams

    async def _role_index(self) -> dict[str, int]:
        if self._roles is None:
            rows = await self.db.execute(
                select(Role.id, Role.name, Role.code).where(
                    Role.tenant_id == self.tenant_id, Role.deleted_at.is_(None)
                )
            )
            index: dict[str, int] = {}
            for role_id, name, code in rows.all():
                for key in (name, code):
                    if key:
                        index[str(key).strip().lower()] = int(role_id)
            self._roles = index
        return self._roles

    async def _username_taken(self, username: str) -> bool:
        # 用户名是全局唯一的（见 UserService.create_user），所以不能只查本租户
        found = await self.db.scalar(
            select(func.count()).select_from(User).where(func.lower(User.username) == username.lower())
        )
        return bool(found)

    async def run(self, content: str, *, dry_run: bool = True) -> ImportOutcome:
        rows, header_errors = parse_csv(content)
        outcome = ImportOutcome(dry_run=dry_run, header_errors=header_errors)
        if header_errors:
            return outcome

        teams = await self._team_index()
        roles = await self._role_index()
        service = UserService(self.db)

        # 文件内部的重复：同一份表格里出现两次同一个账号，第二次要报出来，
        # 否则第一次建成功、第二次静默失败，看结果时对不上数。
        seen: set[str] = set()
        outcome.total = len(rows)

        for row in rows:
            line = int(row.get("__line__") or 0)
            username = (row.get("username") or "").strip()
            result = RowOutcome(line=line, username=username, status="error")

            if not username:
                result.message = "账号为空"
            elif not _USERNAME_RE.match(username):
                result.message = "账号只能用字母、数字、点、下划线、连字符，长度 2-50"
            elif username.lower() in seen:
                result.message = "同一份文件里重复出现"
            elif await self._username_taken(username):
                result.status = "skipped"
                result.message = "账号已存在，本次跳过"
            else:
                team_raw = (row.get("team") or "").strip()
                role_raw = (row.get("role") or "").strip()
                team_id = teams.get(team_raw.lower()) if team_raw else None
                role_id = roles.get(role_raw.lower()) if role_raw else None

                if team_raw and team_id is None:
                    result.message = f"找不到团队「{team_raw}」，请先在团队管理里创建"
                elif role_raw and role_id is None:
                    result.message = f"找不到角色「{role_raw}」"
                else:
                    result.status = "created"
                    result.resolved_team = team_raw or None
                    result.resolved_role = role_raw or None
                    password = generate_initial_password()
                    if dry_run:
                        result.message = "预演通过，尚未写入"
                    else:
                        try:
                            await service.create_user(
                                UserCreate(
                                    username=username,
                                    password=password,
                                    nickname=(row.get("nickname") or "").strip() or username,
                                    phone=(row.get("phone") or "").strip() or None,
                                    email=(row.get("email") or "").strip() or None,
                                    remark=(row.get("remark") or "").strip() or None,
                                    role_ids=[role_id] if role_id else [],
                                    team_ids=[team_id] if team_id else [],
                                ),
                                tenant_id=self.tenant_id,
                                created_by=self.actor_id,
                            )
                        except Exception as exc:  # noqa: BLE001 - 单行失败不该拖垮整份文件
                            logger.warning(
                                "user_import_row_failed", line=line, username=username, error=str(exc)
                            )
                            result.status = "error"
                            result.message = str(exc)[:200]
                        else:
                            result.initial_password = password
                            result.message = "已创建"

            if result.status == "created":
                outcome.created += 1
                seen.add(username.lower())
            elif result.status == "skipped":
                outcome.skipped += 1
                seen.add(username.lower())
            else:
                outcome.failed += 1
            outcome.rows.append(result)

        return outcome


def template_csv() -> str:
    """给业务同事的模板。表头用中文，附一行示例。"""
    return (
        "账号,姓名,手机,邮箱,团队,角色,备注\n"
        "zhangsan,张三,13800000001,zhangsan@example.com,示例团队,成员,\n"
        "lisi,李四,13800000002,,示例团队,成员,\n"
        "wangwu,王五,13800000003,,示例团队,负责人,兼任负责人\n"
    )
