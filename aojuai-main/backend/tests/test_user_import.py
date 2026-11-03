"""CSV 批量导入用户。

重点不在"能不能建出用户"，而在三件容易出事的事：
预演真的不写库、重跑不产生重复、以及一行坏数据不会拖垮整份文件。
"""

from __future__ import annotations

import pytest

from app.domain.users.import_service import (
    MAX_ROWS,
    generate_initial_password,
    parse_csv,
)


def test_header_accepts_chinese_and_english() -> None:
    """给业务同事的模板用中文表头，给脚本用英文——两种都得认。"""
    zh, errors = parse_csv("账号,姓名,手机,团队,角色\nzhangsan,张三,13800000001,一组,组员\n")
    assert not errors
    assert zh[0]["username"] == "zhangsan"
    assert zh[0]["nickname"] == "张三"
    assert zh[0]["team"] == "一组"

    en, errors = parse_csv("username,nickname,phone,team,role\nlisi,李四,13800000002,一组,组员\n")
    assert not errors
    assert en[0]["username"] == "lisi"


def test_unknown_columns_are_ignored_not_rejected() -> None:
    """业务同事的表格里常有"序号""入职日期"这类无关列。

    为它们报错只会让人困惑——他会以为是自己填错了。忽略即可。
    """
    rows, errors = parse_csv("序号,账号,入职日期,姓名\n1,zhangsan,2026-01-01,张三\n")
    assert not errors
    assert rows[0]["username"] == "zhangsan"
    assert "入职日期" not in rows[0]


def test_missing_required_column_is_a_header_error() -> None:
    """缺账号列是整份文件的问题，不该逐行报——逐行报会刷出 200 条一样的错误。"""
    rows, errors = parse_csv("姓名,手机\n张三,13800000001\n")
    assert rows == []
    assert errors and "账号" in errors[0]


def test_blank_lines_are_skipped() -> None:
    """表格末尾的空行很常见，跳过而不是报错。"""
    rows, errors = parse_csv("账号\nzhangsan\n\n\nlisi\n")
    assert not errors
    assert [r["username"] for r in rows] == ["zhangsan", "lisi"]


def test_bom_is_stripped() -> None:
    """Excel 存 UTF-8 CSV 会带 BOM，不处理的话第一列表头永远认不出来。"""
    rows, errors = parse_csv("﻿账号,姓名\nzhangsan,张三\n")
    assert not errors
    assert rows[0]["username"] == "zhangsan"


def test_row_limit_is_enforced() -> None:
    content = "账号\n" + "\n".join(f"user{i}" for i in range(MAX_ROWS + 5))
    rows, errors = parse_csv(content)
    assert rows == []
    assert errors and str(MAX_ROWS) in errors[0]


def test_generated_password_meets_strength_rules() -> None:
    """不接受 CSV 里填明文密码——那份文件会躺在邮箱和下载目录里。

    生成的密码要能过 UserCreate 的强度校验，否则导入会在最后一步才失败。
    """
    from app.domain.users.schemas import UserCreate

    for _ in range(20):
        password = generate_initial_password()
        # 直接走真实的校验路径，而不是自己再抄一遍规则
        UserCreate(username="probe_user", password=password, nickname="probe")


@pytest.mark.parametrize(
    "content,expected",
    [
        ("账号\n \n", 0),          # 只有空白的行
        ("账号\nzhangsan\n", 1),
    ],
)
def test_whitespace_only_rows_do_not_count(content: str, expected: int) -> None:
    rows, _ = parse_csv(content)
    assert len(rows) == expected
