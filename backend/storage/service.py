"""Storage service interface."""

from abc import ABC, abstractmethod

from storage.models import StoredObject


class StorageService(ABC):
    """Contract for all file storage providers."""

    @abstractmethod
    def put_bytes(
        self,
        *,
        document_id: str,
        file_name: str,
        content_type: str,
        data: bytes,
    ) -> StoredObject:
        """Store raw bytes and return generic storage metadata."""

    @abstractmethod
    def get_bytes(self, *, storage_key: str) -> bytes:
        """Fetch stored bytes by storage key."""

    @abstractmethod
    def delete(self, *, storage_key: str) -> None:
        """Delete a stored object by storage key."""

    @abstractmethod
    def exists(self, *, storage_key: str) -> bool:
        """Return whether an object exists for the given key."""
