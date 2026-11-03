"""AOJU Backend - External Messaging Infrastructure

Provides pluggable senders for channels like SMS and Email.
"""

from app.infrastructure.messaging.senders import (
    Message,
    MessageSender,
    SendResult,
    create_sender,
)
from app.infrastructure.messaging.smtp_config import SmtpConfig

__all__ = [
    "Message",
    "MessageSender",
    "SendResult",
    "SmtpConfig",
    "create_sender",
]
