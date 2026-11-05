"""
API Key 服务

密钥格式：aoju_sk_<48位hex>。明文只在创建时返回一次。
"""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError, UnauthorizedError
from app.domain.auth.api_key_models import ApiKey

KEY_PLAINTEXT_PREFIX = "aoju_sk_"
MAX_KEYS_PER_USER = 20

# 未显式指定 scopes 时的默认限制：培训管理全部子模块
# （与 core/feature_switches.py 中 training 模块的 api_prefixes 对齐）
DEFAULT_TRAINING_SCOPES = [
    "/api/v1/training",
    "/api/v1/courses",
    "/api/v1/teachers",
    "/api/v1/companies",
    "/api/v1/schedules",
    "/api/v1/rooms",
    "/api/v1/projects",
    "/api/v1/templates",
    "/api/v1/forms",
    "/api/v1/discussion",
    "/api/v1/my/training",
    "/api/v1/my/project-center",
    "/api/v1/my/teaching",
    "/api/v1/my/vendor",
]

#: 消息中转的入站前缀。**不在默认集合里**——默认集合是"没显式指定 scope 时发什么"，
#: 而中转凭据要给外部系统用，必须显式声明，不能靠默认继承到手。
#: 反过来也一样：一个为培训创建的 key 不该顺带获得往外发消息的能力。
MESSAGE_RELAY_SCOPES = ["/api/v1/message-relay"]

# 允许自定义 scope 的前缀白名单。禁止空列表/全局前缀，
# 防止「畸形 scope 被静默丢弃 → 空列表被当作不限制」而得到全站机器凭证。
ALLOWED_SCOPE_PREFIXES = frozenset(DEFAULT_TRAINING_SCOPES) | frozenset(MESSAGE_RELAY_SCOPES)


def _normalize_scopes(scopes: list[str] | None) -> list[str]:
    """校验并规范化 scope。None → 默认全集；显式列表必须非空且每项在白名单内。"""
    if scopes is None:
        return list(DEFAULT_TRAINING_SCOPES)

    cleaned: list[str] = []
    for raw in scopes:
        if not isinstance(raw, str):
            raise BusinessError(message=f"scope 必须是字符串: {raw!r}")
        value = raw.strip()
        if not value:
            continue
        if value not in ALLOWED_SCOPE_PREFIXES:
            raise BusinessError(
                message=(
                    f"scope 不在允许范围: {value}。"
                    f"允许的前缀：{', '.join(sorted(ALLOWED_SCOPE_PREFIXES))}"
                )
            )
        if value not in cleaned:
            cleaned.append(value)

    if not cleaned:
        raise BusinessError(message="scopes 不能为空（空列表会被视为不限制）；请指定允许的接口前缀或省略以使用默认全集")
    return cleaned


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ApiKeyService:
    """API Key 服务"""

    @staticmethod
    async def create_key(
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        name: str,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> tuple[ApiKey, str]:
        """创建 API Key，返回 (记录, 明文)。明文只此一次。"""
        count_result = await db.execute(
            select(ApiKey).where(
                ApiKey.tenant_id == tenant_id,
                ApiKey.user_id == user_id,
                ApiKey.deleted_at.is_(None),
            )
        )
        if len(list(count_result.scalars().all())) >= MAX_KEYS_PER_USER:
            raise BusinessError(message=f"API Key 数量已达上限 {MAX_KEYS_PER_USER}，请先吊销不用的")

        plaintext = KEY_PLAINTEXT_PREFIX + secrets.token_hex(24)
        normalized_scopes = _normalize_scopes(scopes)
        api_key = ApiKey(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            key_prefix=plaintext[: len(KEY_PLAINTEXT_PREFIX) + 6],
            key_hash=_hash_key(plaintext),
            scopes=normalized_scopes,
            expires_at=(
                _utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
            ),
        )
        db.add(api_key)
        await db.flush()
        await db.refresh(api_key)
        return api_key, plaintext

    @staticmethod
    async def list_keys(db: AsyncSession, tenant_id: int, user_id: int) -> list[ApiKey]:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.tenant_id == tenant_id,
                ApiKey.user_id == user_id,
                ApiKey.deleted_at.is_(None),
            ).order_by(ApiKey.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def revoke_key(db: AsyncSession, tenant_id: int, user_id: int, key_id: int) -> None:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.tenant_id == tenant_id,
                ApiKey.user_id == user_id,
                ApiKey.deleted_at.is_(None),
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise NotFoundError(resource="ApiKey", resource_id=key_id)
        api_key.deleted_at = _utcnow()
        await db.flush()

    @staticmethod
    async def validate_key(
        db: AsyncSession, plaintext: str, request_path: str
    ) -> ApiKey:
        """校验 API Key（存在/过期/scope 前缀），返回 key 记录。用户加载由调用方负责。"""
        if not plaintext.startswith(KEY_PLAINTEXT_PREFIX):
            raise UnauthorizedError(message="Invalid API key")

        result = await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == _hash_key(plaintext),
                ApiKey.deleted_at.is_(None),
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise UnauthorizedError(message="Invalid API key")

        if api_key.expires_at is not None and api_key.expires_at < _utcnow():
            raise UnauthorizedError(message="API key expired")

        # 纵深防御：空 scopes 不再等于"不限制"，退化为默认培训集合，
        # 避免历史遗留或异常写入的空 scope key 变成全站凭证。
        scopes = api_key.scopes or list(DEFAULT_TRAINING_SCOPES)
        if not any(request_path.startswith(prefix) for prefix in scopes):
            raise UnauthorizedError(message="API key scope does not allow this endpoint")

        # 心跳节流：5 分钟内不重复写
        now = _utcnow()
        if api_key.last_used_at is None or (now - api_key.last_used_at).total_seconds() > 300:
            api_key.last_used_at = now
            await db.flush()

        return api_key
