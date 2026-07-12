"""Local filesystem storage provider."""

from hashlib import sha256
from pathlib import Path

from storage.models import StoredObject
from storage.service import StorageService


class LocalStorageService(StorageService):
    """Store objects on local filesystem under configured root."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        *,
        document_id: str,
        file_name: str,
        content_type: str,
        data: bytes,
    ) -> StoredObject:
        safe_name = Path(file_name).name
        storage_key = f"documents/{document_id}/{safe_name}"
        destination = self._root / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        checksum = sha256(data).hexdigest()
        return StoredObject(
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(data),
            checksum=checksum,
            backend="local",
        )

    def get_bytes(self, *, storage_key: str) -> bytes:
        return (self._root / storage_key).read_bytes()

    def delete(self, *, storage_key: str) -> None:
        target = self._root / storage_key
        if target.exists():
            target.unlink()

    def exists(self, *, storage_key: str) -> bool:
        return (self._root / storage_key).exists()
