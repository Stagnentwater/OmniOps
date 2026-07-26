"""Storage provider factory."""

from config.settings import get_settings
from storage.azure_blob_storage import AzureBlobStorageService
from storage.local_storage import LocalStorageService
from storage.s3_storage import S3StorageService
from storage.service import StorageService


def get_storage_service() -> StorageService:
    """Return the configured storage provider implementation."""
    settings = get_settings()
    backend = settings.storage.backend.lower()
    if backend == "local":
        return LocalStorageService(root_path=settings.storage.local_root)
    if backend == "azure_blob":
        return AzureBlobStorageService()
    if backend == "s3":
        return S3StorageService()
    raise ValueError(f"Unsupported storage backend: {settings.storage.backend}")
