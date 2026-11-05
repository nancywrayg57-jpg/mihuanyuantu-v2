"""Adapters for realphotos (storage first in S0)."""

from .storage import LocalDiskStorageAdapter, StorageAdapter, get_storage_adapter

__all__ = ["LocalDiskStorageAdapter", "StorageAdapter", "get_storage_adapter"]
