"""Azure Blob storage provider placeholder for future implementation."""

from storage.models import StoredObject
from storage.service import StorageService


class AzureBlobStorageService(StorageService):
    """Placeholder implementation for Azure Blob backend."""

    def put_bytes(
        self,
        *,
        document_id: str,
        file_name: str,
        content_type: str,
        data: bytes,
    ) -> StoredObject:
        raise NotImplementedError("Azure Blob storage is not implemented in MVP.")

    def get_bytes(self, *, storage_key: str) -> bytes:
        raise NotImplementedError("Azure Blob storage is not implemented in MVP.")

    def delete(self, *, storage_key: str) -> None:
        raise NotImplementedError("Azure Blob storage is not implemented in MVP.")

    def exists(self, *, storage_key: str) -> bool:
        raise NotImplementedError("Azure Blob storage is not implemented in MVP.")
