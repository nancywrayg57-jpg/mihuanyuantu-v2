"""bind message channels to the gateway account that owns them

Revision ID: base_20260821_channel_gateway_owner
Revises: base_20260820_gateway_auth
Create Date: 2026-08-21

HMAC 签名只证明"某个合法网关"，不证明"这个用户所属的网关"。
而 `message_gateway_accounts` 没有 tenant_id、是全局共享的，同一渠道类型可以有
多个 active 账号——不限定归属的话，持有账号 A 密钥的运行时可以声称任意
`external_user_id`，驱动**任何租户**下匹配到的渠道（包括注入该用户的 AI 助手）。

本次给渠道加上"是被哪个网关账号绑的"，入站解析据此限定。

**存量为 NULL**：本次之前绑定的渠道没有这个字段，它们会在下一次
通过签名鉴权的入站里被认领（见 `record_inbound_message`）。
不预先回填是有意的：我们并不知道存量渠道当初是被哪个账号绑的，
猜一个填进去比留空更危险。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

revision: str = "base_20260821_channel_gateway_owner"
down_revision: str | None = "base_20260820_gateway_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "user_message_channels"
_COLUMN = "gateway_account_id"
_INDEX = "ix_user_message_channels_gateway_account_id"


def _inspector() -> Inspector:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if _TABLE not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns(_TABLE)}
    if _COLUMN not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.BigInteger(),
                nullable=True,
                comment=(
                    "绑定这条渠道的网关账号ID。入站解析时用它限定归属——"
                    "签名只证明'某个合法网关'，不证明'这个用户所属的网关'"
                ),
            ),
        )
    if not any(item["name"] == _INDEX for item in _inspector().get_indexes(_TABLE)):
        op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    inspector = _inspector()
    if _TABLE not in inspector.get_table_names():
        return
    if any(item["name"] == _INDEX for item in inspector.get_indexes(_TABLE)):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _COLUMN in {item["name"] for item in inspector.get_columns(_TABLE)}:
        op.drop_column(_TABLE, _COLUMN)
