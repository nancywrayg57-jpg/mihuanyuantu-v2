"""Optional downstream entry point for other modules (e.g. the public-site contact form).

依赖方向是**单向**的：别的模块可以在守卫后调用这里，support 永远不 import 它们。
所以本文件的入参全是原始标量，没有一个 CMS/业务类型——签名里出现对方的类型，
就等于把可选联动写成了硬依赖。

调用方的义务（见 `app/api/v1/endpoints/cms_public.py`）：
先 `is_module_installed("support")`，再 `is_module_enabled_for_tenant(...)`，
两者都成立才**延迟 import** 本模块。未安装时连 import 都不该发生。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .constants import DEFAULT_CATEGORY, PUBLIC_CONTACT_RELATED_TYPE
from .models import SupportTicket
from .service import SupportService


async def create_ticket_from_public_contact(
    db: AsyncSession,
    *,
    tenant_id: int,
    name: str,
    email: str,
    message: str,
    company: str | None = None,
    source_page: str | None = None,
    subject: str | None = None,
    category: str | None = None,
    submission_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> SupportTicket:
    """Turn one anonymous contact submission into a ticket.

    留言记录与工单**都保留**：留言是公开站的原始提交（有独立的合规意义），
    工单是处理流程，职责不同。两者靠 `related_id` 互相定位。
    """
    lines = [message.strip(), "", f"Name: {name.strip()}", f"Email: {email.strip()}"]
    if company:
        lines.append(f"Company: {company.strip()}")
    if source_page:
        lines.append(f"Source page: {source_page.strip()}")

    payload: dict[str, Any] = {
        "source": "public_contact",
        "contact": {
            "name": name,
            "email": email,
            "company": company,
            "sourcePage": source_page,
        },
    }
    if submission_id is not None:
        payload["submissionId"] = int(submission_id)
    if extra:
        payload.update(extra)

    return await SupportService(db).create_anonymous_ticket(
        tenant_id=tenant_id,
        subject=(subject or "").strip() or f"Public contact: {name.strip()}",
        description="\n".join(lines).strip(),
        category=(category or DEFAULT_CATEGORY),
        related_type=PUBLIC_CONTACT_RELATED_TYPE,
        related_id=str(submission_id) if submission_id is not None else None,
        extra=payload,
    )


__all__ = ["create_ticket_from_public_contact"]
