"""Storage domain models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredObject:
    """Generic object metadata returned by storage providers."""

    storage_key: str
    content_type: str
    size_bytes: int
    checksum: str
    backend: str
