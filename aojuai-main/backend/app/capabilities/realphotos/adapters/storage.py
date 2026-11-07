"""StorageAdapter contract + LocalDisk implementation (S0).

OSS 仅预留接口位，首版不启用。网关经适配器流式读取，禁止向客户暴露裸路径。
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

    def ensure_seed_file(self) -> StoredObject:
        """grill Q6：开发种子文件（非客户数据）供网关取证。"""
        return self.put_bytes(
            SEED_OBJECT_KEY,
            SEED_OBJECT_BYTES,
            content_type="text/plain; charset=utf-8",
        )


def get_storage_adapter() -> LocalDiskStorageAdapter:
    return LocalDiskStorageAdapter()
