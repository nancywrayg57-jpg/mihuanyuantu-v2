"""
AOJU Backend - Core Configuration
"""
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _normalize_pool_profile(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if "worker" in normalized:
        return "worker"
    if normalized in {"web", "api", "server", "uvicorn"}:
        return "web"
    return None


def _looks_like_worker_process() -> bool:
    main_module = sys.modules.get("__main__")
    main_spec = getattr(main_module, "__spec__", None)
    main_name = str(getattr(main_spec, "name", "") or "").strip().lower()
    if main_name.endswith("_worker"):
        return True

    argv0 = Path(str(sys.argv[0] or "")).stem.strip().lower()
    return argv0.endswith("_worker")


def _database_application_name(process_role: str | None = None) -> str:
    """PG `application_name`：`aojuai:<角色>`，让 pg_stat_activity 能按进程（web/worker）归属连接。"""
    main_module = sys.modules.get("__main__")
    main_spec = getattr(main_module, "__spec__", None)
    main_name = str(getattr(main_spec, "name", "") or "").strip()
    raw = (
        str(process_role or os.getenv("AOJU_PROCESS_ROLE") or "").strip()
        or main_name
        or Path(str(sys.argv[0] or "web")).stem
        or "web"
    )
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-.") or "web"
    return f"aojuai:{normalized}"[:63]


class Settings(BaseSettings):
    """Application Settings"""

    model_config = SettingsConfigDict(
        # Always resolve `.env` relative to `backend/`, not the current working directory.
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "AOJUAI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENV: Literal["development", "staging", "production"] = "development"

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = "127.0.0.1"

    # Multi-tenant / Public registration
    DEFAULT_TENANT_CODE: str = "default"

    # Public CMS site routing is deployment-level and opt-in.  The frontend
    # consumes the corresponding NEXT_PUBLIC_PUBLIC_SITE_ROUTING_MODE value.
    PUBLIC_SITE_ROUTING_MODE: Literal["off", "domain", "path"] = "off"
    PUBLIC_SITE_DOMAINS: str = ""
    # Development-only public tenant fallback.  An unset value means that even
    # development requests must resolve an explicitly configured domain.
    CMS_DEFAULT_TENANT_CODE: str | None = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8848"]

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_USER: str = "aoju"
    DB_PASSWORD: str = "aoju_password_change_me"
    DB_NAME: str = "aoju"
    DB_ECHO: bool = False
    # 轻量部署：DB_DRIVER=sqlite 时整个内核跑在单文件 SQLite 上（无 PostgreSQL/Redis 依赖的单机档）。
    # 只有 L0/L1 内核保证双方言；L2 业务包可以声明 PostgreSQL-only。
    DB_DRIVER: str = "postgresql"
    SQLITE_PATH: str = "./data/aoju.db"
    # SQLite 事务起始：immediate（缺省，事务串行化，"先读后写"永不丢更新也不报 BUSY；代价是长事务会让其他事务排队）
    # | deferred（读不占写锁，吞吐更好；"先读后写"遇并发写以 database is locked 报错而非静默丢失）
    SQLITE_BEGIN_MODE: Literal["deferred", "immediate"] = "immediate"
    DATABASE_URL_OVERRIDE: str | None = None

    # 连接池。原来硬编码 10/20，高并发部署无法调整；一律走 Settings，不直接读取环境变量。
    # web/worker 分池（回流自 nextjs-plugins）：API 进程与后台 worker 进程的连接
    # 需求量级不同，共用一档会让 worker 空占连接或 web 被挤兑。
    # *_WEB 为 None 时回落到通用档；worker 默认低配。
    AOJU_PROCESS_ROLE: str | None = None
    AOJU_DB_POOL_PROFILE: str | None = None
    DB_POOL_SIZE_WEB: int | None = None
    DB_MAX_OVERFLOW_WEB: int | None = None
    DB_POOL_TIMEOUT_WEB: int | None = None
    DB_POOL_RECYCLE_WEB: int | None = None
    DB_POOL_SIZE_WORKER: int = 4
    DB_MAX_OVERFLOW_WORKER: int = 4
    DB_POOL_TIMEOUT_WORKER: int = 15
    DB_POOL_RECYCLE_WORKER: int | None = None
    # 空闲会话回收（PG14+ idle_session_timeout）：web 10 分钟、worker 5 分钟；0 关闭
    DB_IDLE_SESSION_TIMEOUT_WEB: int | None = 600
    DB_IDLE_SESSION_TIMEOUT_WORKER: int | None = 300
    DB_IDLE_SESSION_TIMEOUT: int = 600

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    @computed_field
    @property
    def ACTIVE_DB_POOL_PROFILE(self) -> Literal["web", "worker"]:
        explicit = _normalize_pool_profile(self.AOJU_DB_POOL_PROFILE)
        if explicit is not None:
            return explicit
        explicit = _normalize_pool_profile(self.AOJU_PROCESS_ROLE)
        if explicit is not None:
            return explicit
        return "worker" if _looks_like_worker_process() else "web"

    def _pool_value(self, *, common: int, web: int | None, worker: int | None) -> int:
        if self.ACTIVE_DB_POOL_PROFILE == "worker":
            return int(worker if worker is not None else common)
        return int(web if web is not None else common)

    @computed_field
    @property
    def DB_POOL_SIZE_EFFECTIVE(self) -> int:
        # 分池取值后套内核契约边界，防止误配打爆连接数。
        return max(1, min(200, self._pool_value(
            common=self.DB_POOL_SIZE, web=self.DB_POOL_SIZE_WEB, worker=self.DB_POOL_SIZE_WORKER,
        )))

    @computed_field
    @property
    def DB_MAX_OVERFLOW_EFFECTIVE(self) -> int:
        return max(0, min(500, self._pool_value(
            common=self.DB_MAX_OVERFLOW, web=self.DB_MAX_OVERFLOW_WEB, worker=self.DB_MAX_OVERFLOW_WORKER,
        )))

    @computed_field
    @property
    def DB_POOL_TIMEOUT_EFFECTIVE(self) -> int:
        return max(1, min(300, self._pool_value(
            common=self.DB_POOL_TIMEOUT, web=self.DB_POOL_TIMEOUT_WEB, worker=self.DB_POOL_TIMEOUT_WORKER,
        )))

    @computed_field
    @property
    def DB_POOL_RECYCLE_EFFECTIVE(self) -> int:
        # -1 = 不回收（SQLAlchemy 语义），其余下限 60 秒避免抖动
        value = self._pool_value(
            common=self.DB_POOL_RECYCLE, web=self.DB_POOL_RECYCLE_WEB, worker=self.DB_POOL_RECYCLE_WORKER,
        )
        if value < 0:
            return -1
        return max(60, min(value, 86400))

    @computed_field
    @property
    def DB_IDLE_SESSION_TIMEOUT_EFFECTIVE(self) -> int:
        value = self._pool_value(
            common=self.DB_IDLE_SESSION_TIMEOUT,
            web=self.DB_IDLE_SESSION_TIMEOUT_WEB,
            worker=self.DB_IDLE_SESSION_TIMEOUT_WORKER,
        )
        return max(0, min(value, 86400))

    @computed_field
    @property
    def DB_APPLICATION_NAME_EFFECTIVE(self) -> str:
        return _database_application_name(self.AOJU_PROCESS_ROLE)

    @computed_field
    @property
    def IS_SQLITE(self) -> bool:
        override = (self.DATABASE_URL_OVERRIDE or "").strip()
        if override:
            return override.startswith("sqlite")
        return (self.DB_DRIVER or "postgresql").strip().lower() == "sqlite"

    @computed_field
    @property
    def DB_DIALECT(self) -> Literal["postgresql", "sqlite"]:  # noqa: N802
        return "sqlite" if self.IS_SQLITE else "postgresql"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """Async connection string：PostgreSQL(asyncpg) 或 SQLite(aiosqlite)"""
        override = (self.DATABASE_URL_OVERRIDE or "").strip()
        if override:
            return override
        if self.IS_SQLITE:
            path = (self.SQLITE_PATH or "").strip() or "./data/aoju.db"
            return "sqlite+aiosqlite:///:memory:" if path == ":memory:" else f"sqlite+aiosqlite:///{path}"
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @computed_field
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync connection string (for Alembic)"""
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite"):
            return url.replace("sqlite+aiosqlite", "sqlite", 1)
        if url.startswith("postgresql+asyncpg"):
            return url.replace("postgresql+asyncpg", "postgresql", 1)
        return url

    # Redis
    # Redis 是否启用：None = 自动（轻量档 SQLite 关、标准档开）。关闭时运行时缓存只走进程内本地缓存，
    # 不发起任何连接、不打降级日志——轻量档"零外部依赖"。多进程/多实例部署必须开。
    REDIS_ENABLED: bool | None = None
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    # 缓存键命名空间：同机多实例共享 Redis 时防止跨实例键碰撞（menu_routes 等
    # 键形只含 tenant/user id，各实例的 tenant 1/user 1 会互读脏缓存）。
    # 默认取 DB_NAME（每实例数据库名唯一）；显式设置 AOJU_CACHE_NAMESPACE 可覆盖。
    AOJU_CACHE_NAMESPACE: str = ""

    @computed_field
    @property
    def CACHE_NAMESPACE(self) -> str:  # noqa: N802 - 与本文件计算字段命名约定一致
        explicit = str(self.AOJU_CACHE_NAMESPACE or "").strip()
        if explicit:
            return explicit
        if self.IS_SQLITE:
            # 轻量档：按库文件路径隔离。缺省 DB_NAME 往往与同机 PG 实例相同，共用 Redis 时会互相投毒
            import hashlib

            digest = hashlib.sha1(str(self.DATABASE_URL).encode("utf-8")).hexdigest()[:8]
            return f"sqlite-{digest}"
        return str(self.DB_NAME or "aoju").strip()

    @computed_field
    @property
    def DEPLOY_PROFILE(self) -> Literal["lite", "standard"]:  # noqa: N802
        """部署形态：lite = SQLite 单机（无 Redis、单进程）；standard = PostgreSQL + Redis。由 DB_DRIVER 决定。"""
        return "lite" if self.IS_SQLITE else "standard"

    @computed_field
    @property
    def REDIS_ENABLED_EFFECTIVE(self) -> bool:  # noqa: N802
        if self.REDIS_ENABLED is None:
            return not self.IS_SQLITE
        return bool(self.REDIS_ENABLED)

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        """Redis connection string"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 180
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PROVIDER_SECRET_KEY: str | None = None
    AUTH_ACCESS_COOKIE_NAME: str = "aoju_access_token"
    AUTH_REFRESH_COOKIE_NAME: str = "aoju_refresh_token"
    AUTH_COOKIE_DOMAIN: str | None = None
    AUTH_COOKIE_SECURE: bool | None = None
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # Security
    PASSWORD_MIN_LENGTH: int = 8
    AOJ_PROXY_SHARED_SECRET: str | None = None

    # SMTP (empty host/from means SMTP is not configured)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str | None = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: float = 10.0

    # File Upload
    UPLOAD_DIR: str = "static/uploads"
    STATIC_URL: str = "/static"
    MAX_UPLOAD_SIZE_MB: int = 5

    # Development helpers
    AUTO_INIT_DB: bool = False
    AUTO_SEED_DATA: bool = False

    # Scheduler
    SCHEDULER_ENABLED: bool = True
    EXAMPLE_TASK_ENABLED: bool = False
    MESSAGE_GATEWAY_TASKS_ENABLED: bool = False
    # Message gateway background polling / inbound auth（回流自 nextjs-plugins 4259052e）
    MESSAGE_GATEWAY_POLL_INTERVAL_SECONDS: int = 20
    MESSAGE_GATEWAY_WECHAT_GET_UPDATES_TIMEOUT_SECONDS: float = 12.0
    # 入站默认 fail-closed：未签名请求一律拒绝；只在灰度旧网关运行时才临时放开，
    # 且每一次未签名放行都会打 CRITICAL 事件。
    MESSAGE_GATEWAY_ALLOW_UNSIGNED_INBOUND: bool = False
    MESSAGE_GATEWAY_SIGNATURE_TTL_SECONDS: int = 300

    # Installed optional modules (comma-separated, e.g. "speech" / "none")
    AOJ_ENABLED_MODULES: str = ""

    # realphotos capability knobs (optional; empty = package defaults)
    REALPHOTOS_ALLOW_DEV_CAPTCHA: str = ""
    REALPHOTOS_STORAGE_ROOT: str = ""

    # 各 worker 的并发度，形如 "code:2,other_code:4"。
    # 用**一个**通用字段而不是每个 worker 一个字段：Settings 是 pydantic 模型、
    # 拒绝未声明字段，如果每个 worker 都要往这里加一行，就等于"加模块必须改中央文件"，
    # 与能力包的设计原则直接冲突。没列到的 worker 用它声明里的 default_concurrency。
    AOJ_WORKER_CONCURRENCY: str = ""

    # Route filter (comma/space/newline separated, e.g. "/speech/demo,/foo")
    AOJ_ROUTE_EXCLUDE_PATHS: str = ""

    @property
    def is_pytest_runtime(self) -> bool:
        """Keep the dynamic pytest marker behind the Settings boundary."""
        return bool(os.environ.get("PYTEST_CURRENT_TEST"))


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
