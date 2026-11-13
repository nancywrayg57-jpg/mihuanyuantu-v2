"""StorageAdapter contract + LocalDisk default + OSS stub (AD-007).

OSS 仅预留实现类；未配置凭证时不得启用。首版默认 LocalDisk。
网关经适配器流式读取，禁止向客户暴露裸路径。本工单禁止接真桶上线。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from app.capabilities.realphotos.constants import (
    SEED_OBJECT_BYTES,
    SEED_OBJECT_KEY,
    storage_root,
)
from app.core.config import settings
from app.core.exceptions import BusinessError, NotFoundError

_OBJECT_KEY_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


@dataclass(frozen=True, slots=True)
class StoredObject:
    object_key: str
    size: int
    content_type: str


class StorageAdapter(Protocol):
    def put_bytes(
        self, object_key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> StoredObject: ...

    def open_read(self, object_key: str) -> BinaryIO: ...

    def exists(self, object_key: str) -> bool: ...

    def delete(self, object_key: str) -> bool: ...

    def ensure_seed_file(self) -> StoredObject: ...


class LocalDiskStorageAdapter:
    """首版默认 LocalDisk；根目录仅服务端可知。"""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or storage_root()).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, object_key: str) -> Path:
        key = (object_key or "").strip().lstrip("/")
        if not key or not _OBJECT_KEY_RE.fullmatch(key) or ".." in key.split("/"):
            raise BusinessError(message="非法对象键", code="INPUT_INVALID")
        path = (self._root / key).resolve()
        if self._root not in path.parents and path != self._root:
            raise BusinessError(message="非法对象键", code="INPUT_INVALID")
        return path

    def put_bytes(
        self, object_key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> StoredObject:
        path = self._resolve(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(object_key=object_key, size=len(data), content_type=content_type)

    def open_read(self, object_key: str) -> BinaryIO:
        path = self._resolve(object_key)
        if not path.is_file():
            raise NotFoundError(message="对象不存在")
        return path.open("rb")

    def exists(self, object_key: str) -> bool:
        try:
            return self._resolve(object_key).is_file()
        except BusinessError:
            return False

    def delete(self, object_key: str) -> bool:
        """Remove object if present. Idempotent; missing key → False."""
        try:
            path = self._resolve(object_key)
        except BusinessError:
            return False
        if not path.is_file():
            return False
        path.unlink()
        return True

    def list_library_object_keys(self, *, prefixes: tuple[str, ...] = ("upload", "generation")) -> list[str]:
        """List LocalDisk keys under tenant/*/upload|generation (server-only; never expose paths)."""
        allowed = {str(p).strip() for p in prefixes if str(p).strip()}
        if not allowed:
            return []
        keys: list[str] = []
        tenant_root = self._root / "tenant"
        if not tenant_root.is_dir():
            return keys
        for tenant_dir in tenant_root.iterdir():
            if not tenant_dir.is_dir():
                continue
            for purpose in allowed:
                purpose_dir = tenant_dir / purpose
                if not purpose_dir.is_dir():
                    continue
                for path in purpose_dir.rglob("*"):
                    if not path.is_file():
                        continue
                    try:
                        rel = path.relative_to(self._root).as_posix()
                    except ValueError:
                        continue
                    if ".." in rel.split("/"):
                        continue
                    keys.append(rel)
        return keys

    def ensure_seed_file(self) -> StoredObject:
        """grill Q6：开发种子文件（非客户数据）供网关取证。"""
        return self.put_bytes(
            SEED_OBJECT_KEY,
            SEED_OBJECT_BYTES,
            content_type="text/plain; charset=utf-8",
        )


class OssStorageAdapter:
    """AD-007 OSS 适配器预留。

    未配置 endpoint/bucket/access_key/secret 时构造即失败，禁止静默当 LocalDisk。
    本工单不实现真上传下载；方法调用抛 OSS_NOT_IMPLEMENTED，避免误接生产桶。
    """

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        access_key_secret: str,
        prefix: str = "",
    ) -> None:
        missing = [
            name
            for name, value in (
                ("endpoint", endpoint),
                ("bucket", bucket),
                ("access_key_id", access_key_id),
                ("access_key_secret", access_key_secret),
            )
            if not str(value or "").strip()
        ]
        if missing:
            raise BusinessError(
                message="OSS 凭证未配置完整，不得启用 OssStorageAdapter",
                code="OSS_NOT_CONFIGURED",
                details={"missing": missing},
            )
        self.endpoint = str(endpoint).strip()
        self.bucket = str(bucket).strip()
        self.access_key_id = str(access_key_id).strip()
        self.access_key_secret = str(access_key_secret).strip()
        self.prefix = str(prefix or "").strip().strip("/")

    def _nyi(self) -> None:
        raise BusinessError(
            message="OSS 适配器仅预留，本工单禁止真桶读写",
            code="OSS_NOT_IMPLEMENTED",
            details={"endpoint": self.endpoint, "bucket": self.bucket},
        )

    def put_bytes(
        self, object_key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> StoredObject:
        self._nyi()
        raise AssertionError("unreachable")

    def open_read(self, object_key: str) -> BinaryIO:
        self._nyi()
        raise AssertionError("unreachable")

    def exists(self, object_key: str) -> bool:
        self._nyi()
        raise AssertionError("unreachable")

    def delete(self, object_key: str) -> bool:
        self._nyi()
        raise AssertionError("unreachable")

    def ensure_seed_file(self) -> StoredObject:
        self._nyi()
        raise AssertionError("unreachable")


def _oss_settings_configured() -> bool:
    return all(
        str(getattr(settings, name, "") or "").strip()
        for name in (
            "REALPHOTOS_OSS_ENDPOINT",
            "REALPHOTOS_OSS_BUCKET",
            "REALPHOTOS_OSS_ACCESS_KEY_ID",
            "REALPHOTOS_OSS_ACCESS_KEY_SECRET",
        )
    )


def get_storage_adapter() -> LocalDiskStorageAdapter | OssStorageAdapter:
    """默认 LocalDisk。仅当 backend=oss 且凭证齐全时返回 OssStorageAdapter（仍不接真桶）。"""
    backend = str(getattr(settings, "REALPHOTOS_STORAGE_BACKEND", "") or "local").strip().lower()
    if backend in {"", "local", "localdisk", "disk"}:
        return LocalDiskStorageAdapter()
    if backend == "oss":
        if not _oss_settings_configured():
            raise BusinessError(
                message="REALPHOTOS_STORAGE_BACKEND=oss 但凭证缺失，拒绝启用",
                code="OSS_NOT_CONFIGURED",
            )
        return OssStorageAdapter(
            endpoint=str(settings.REALPHOTOS_OSS_ENDPOINT),
            bucket=str(settings.REALPHOTOS_OSS_BUCKET),
            access_key_id=str(settings.REALPHOTOS_OSS_ACCESS_KEY_ID),
            access_key_secret=str(settings.REALPHOTOS_OSS_ACCESS_KEY_SECRET),
            prefix=str(getattr(settings, "REALPHOTOS_OSS_PREFIX", "") or ""),
        )
    raise BusinessError(
        message=f"未知存储后端 {backend!r}，仅支持 local|oss",
        code="STORAGE_BACKEND_INVALID",
    )
