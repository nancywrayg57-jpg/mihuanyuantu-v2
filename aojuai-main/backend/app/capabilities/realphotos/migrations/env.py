"""Alembic environment for the isolated realphotos revision chain."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.capabilities.realphotos import CAPABILITY
from app.capabilities.realphotos import models as realphotos_models  # noqa: F401
from app.core.config import settings

config = context.config


def _sync_url() -> str:
    """Alembic 需要同步驱动；本仓安装的是 psycopg2-binary，不是 psycopg v3。"""
    url = str(settings.DATABASE_URL_SYNC)
    if "+psycopg2://" in url or url.startswith("sqlite"):
        return url
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


config.set_main_option("sqlalchemy.url", _sync_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = realphotos_models.RealphotosMerchantProfile.metadata

OWNED_TABLES = {
    "cap_realphotos_merchant_profiles",
    "cap_realphotos_auth_challenges",
    "cap_realphotos_auth_guards",
    "cap_realphotos_credit_accounts",
    "cap_realphotos_credit_ledger_entries",
    "cap_realphotos_execution_jobs",
    "cap_realphotos_outbox",
    "cap_realphotos_copy_execution_guards",
}


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in OWNED_TABLES
    table = getattr(object_, "table", None)
    return table is None or table.name in OWNED_TABLES


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=CAPABILITY.version_table,
        include_object=include_object,
        render_as_batch=str(config.get_main_option("sqlalchemy.url") or "").startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(
            connection=supplied_connection,
            target_metadata=target_metadata,
            version_table=CAPABILITY.version_table,
            include_object=include_object,
            render_as_batch=supplied_connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=CAPABILITY.version_table,
            include_object=include_object,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
