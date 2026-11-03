"""merge speech and message channel heads

Revision ID: base_20260426_merge_speech_and_message_heads
Revises: base_20260424_speech_voice_clone_foundation, base_20260425_user_message_channels
Create Date: 2026-04-26

This revision keeps the base migration graph on a single head after the
speech voice-clone foundation and message-channel migrations landed in
parallel. It does not change schema or data.
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "base_20260426_merge_speech_and_message_heads"
down_revision: Union[str, tuple[str, str], None] = (
    "base_20260424_speech_voice_clone_foundation",
    "base_20260425_user_message_channels",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
