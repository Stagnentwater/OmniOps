"""S3 storage provider placeholder for future implementation."""

from storage.models import StoredObject
from storage.service import StorageService


class S3StorageService(StorageService):
    """Placeholder implementation for S3 backend."""

    def put_bytes(
        self,
        *,
        document_id: str,
        file_name: str,
        content_type: str,
        data: bytes,
    ) -> StoredObject:
        raise NotImplementedError("S3 storage is not implemented in MVP.")

    def get_bytes(self, *, storage_key: str) -> bytes:
        raise NotImplementedError("S3 storage is not implemented in MVP.")

    def delete(self, *, storage_key: str) -> None:
        raise NotImplementedError("S3 storage is not implemented in MVP.")

    def exists(self, *, storage_key: str) -> bool:
        raise NotImplementedError("S3 storage is not implemented in MVP.")
