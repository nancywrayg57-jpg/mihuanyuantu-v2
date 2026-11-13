"""REMAIN-GAP W3/W4：R5 角色认领隔离 · R7 OSS stub · R6 生成物存在性（路径检查）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.capabilities.realphotos.adapters.storage import (
    LocalDiskStorageAdapter,
    OssStorageAdapter,
    get_storage_adapter,
)
from app.capabilities.realphotos.constants import (
    JOB_KIND_INBOX_CLEANUP,
    JOB_KIND_LIBRARY_ORPHAN_CLEANUP,
    JOB_KIND_OUTPUT_CLEANUP,
    JOB_KIND_PROCESS_IMAGE,
    JOB_STATUS_QUEUED,
)
from app.capabilities.realphotos.models import RealphotosExecutionJob
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts
from app.capabilities.realphotos.services.job_service import RealphotosJobService
from app.capabilities.realphotos.worker_roles import CLEANUP_JOB_KINDS, PROCESS_JOB_KINDS
from app.core.config import settings
from app.core.exceptions import BusinessError


def test_r5_role_kind_whitelists() -> None:
    assert JOB_KIND_PROCESS_IMAGE in PROCESS_JOB_KINDS
    assert JOB_KIND_INBOX_CLEANUP not in PROCESS_JOB_KINDS
    assert JOB_KIND_OUTPUT_CLEANUP in CLEANUP_JOB_KINDS
    assert JOB_KIND_LIBRARY_ORPHAN_CLEANUP in CLEANUP_JOB_KINDS
    assert JOB_KIND_PROCESS_IMAGE not in CLEANUP_JOB_KINDS


@pytest.mark.asyncio
async def test_r5_process_does_not_claim_cleanup(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_admin"]["tenantId"])
    jobs = RealphotosJobService(db)
    cleanup_job = await jobs.enqueue(
        tenant_id=tenant,
        owner_account_id=int(summary["rp_admin"]["userId"]),
        job_kind=JOB_KIND_INBOX_CLEANUP,
    )
    await db.flush()
    # 同会话 claim：单测内存库不能走全局 async_session_factory
    claimed = await jobs.claim(worker_id="ut-process", job_kinds=PROCESS_JOB_KINDS)
    assert claimed is None
    still = (
        await db.execute(
            select(RealphotosExecutionJob).where(RealphotosExecutionJob.id == int(cleanup_job.id))
        )
    ).scalar_one()
    assert str(still.status) == JOB_STATUS_QUEUED
    assert still.claimed_by is None


@pytest.mark.asyncio
async def test_r5_cleanup_claims_cleanup_not_process(db) -> None:
    summary = await bootstrap_s0_accounts(db)
    tenant = int(summary["rp_admin"]["tenantId"])
    owner = int(summary["rp_admin"]["userId"])
    jobs = RealphotosJobService(db)
    cleanup_job = await jobs.enqueue(
        tenant_id=tenant, owner_account_id=owner, job_kind=JOB_KIND_INBOX_CLEANUP
    )
    await db.flush()
    claimed = await jobs.claim(worker_id="ut-cleanup", job_kinds=CLEANUP_JOB_KINDS)
    assert claimed is not None
    assert str(claimed.job_kind) == JOB_KIND_INBOX_CLEANUP
    assert int(claimed.id) == int(cleanup_job.id)
    # process 白名单仍不得认领（清理已占用）
    again = await jobs.claim(worker_id="ut-process", job_kinds=PROCESS_JOB_KINDS)
    assert again is None or str(again.job_kind) != JOB_KIND_INBOX_CLEANUP


def test_r7_default_local_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "REALPHOTOS_STORAGE_BACKEND", "local")
    adapter = get_storage_adapter()
    assert isinstance(adapter, LocalDiskStorageAdapter)


def test_r7_oss_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "REALPHOTOS_STORAGE_BACKEND", "oss")
    monkeypatch.setattr(settings, "REALPHOTOS_OSS_ENDPOINT", "")
    monkeypatch.setattr(settings, "REALPHOTOS_OSS_BUCKET", "")
    monkeypatch.setattr(settings, "REALPHOTOS_OSS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(settings, "REALPHOTOS_OSS_ACCESS_KEY_SECRET", "")
    with pytest.raises(BusinessError) as exc:
        get_storage_adapter()
    assert exc.value.code == "OSS_NOT_CONFIGURED"


def test_r7_oss_stub_not_implemented(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OssStorageAdapter(
        endpoint="https://oss.example",
        bucket="demo",
        access_key_id="ak",
        access_key_secret="sk",
    )
    with pytest.raises(BusinessError) as exc:
        adapter.put_bytes("a/b.jpg", b"x")
    assert exc.value.code == "OSS_NOT_IMPLEMENTED"


def test_r6_generated_sdk_files_exist() -> None:
    root = Path(__file__).resolve().parents[4] / "frontend" / "src" / "generated" / "realphotos"
    assert (root / "image_processing.ts").is_file()
    assert (root / "index.ts").is_file()
    text = (root / "image_processing.ts").read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in text
    assert "/api/v1/realphotos/assets" in text


def test_r8_architecture_frontmatter_not_unimplemented() -> None:
    arch = Path(__file__).resolve().parents[5] / "docs" / "蜜獾原图-v2-项目架构-v1.0.md"
    text = arch.read_text(encoding="utf-8")
    assert "implementation_status: s0_s6_coded_partial" in text
    assert "implementation_status: NOT_IMPLEMENTED" not in text.split("---", 2)[1]
