"""Qdrant connection management."""

from __future__ import annotations

from qdrant_client import QdrantClient

from config.settings import QdrantSettings


class QdrantConnectionManager:
    """Manages the Qdrant HTTP client connection.

    Wraps the official qdrant_client.QdrantClient, providing a single
    entry point for obtaining the client instance. Designed for use as
    a long-lived singleton.
    """

    def __init__(self, host: str, port: int) -> None:
        # We use the HTTP REST API by default.
        self._client = QdrantClient(host=host, port=port)

    @classmethod
    def from_settings(cls, settings: QdrantSettings) -> QdrantConnectionManager:
        """Create a connection manager from application settings."""
        return cls(host=settings.host, port=settings.port)

    @property
    def client(self) -> QdrantClient:
        """Return the underlying QdrantClient."""
        return self._client
