"""Application-level connection pool for database clients.

Manages the lifecycle of Neo4j, Qdrant, and PostgreSQL connections
as a single coordinated unit. Created at startup, closed at shutdown.

This replaces per-request connection creation, ensuring:
- Connection reuse across requests
- Proper shutdown/cleanup of all connections
- Single source of truth for client instances
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Holds long-lived database client connections.

    Created once during application startup and stored on `app.state`.
    All connection managers are lazily initialized to handle partial
    infrastructure availability gracefully.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._neo4j_conn: Any = None
        self._qdrant_conn: Any = None
        self._initialized = False

    def initialize(self) -> None:
        """Create all connection managers. Call during app startup.

        Connections that fail to initialize log errors but do not
        prevent the application from starting — other services
        may still be usable.
        """
        if self._initialized:
            logger.warning("ConnectionPool already initialized. Skipping.")
            return

        # Neo4j
        try:
            from graph.neo4j_connection import Neo4jConnectionManager
            self._neo4j_conn = Neo4jConnectionManager(
                uri=self._settings.neo4j.uri,
                user=self._settings.neo4j.user,
                password=self._settings.neo4j.password,
            )
            logger.info("Neo4j connection pool initialized.")
        except Exception as e:
            logger.error("Failed to initialize Neo4j connection: %s", e)
            self._neo4j_conn = None

        # Qdrant
        try:
            from vector.qdrant_connection import QdrantConnectionManager
            self._qdrant_conn = QdrantConnectionManager(
                url=self._settings.qdrant.url,
                api_key=self._settings.qdrant.api_key,
            )
            logger.info("Qdrant connection pool initialized.")
        except Exception as e:
            logger.error("Failed to initialize Qdrant connection: %s", e)
            self._qdrant_conn = None

        self._initialized = True
        logger.info("ConnectionPool initialization complete.")

    @property
    def neo4j(self) -> Any:
        """Return the Neo4j connection manager, or None if unavailable."""
        return self._neo4j_conn

    @property
    def qdrant(self) -> Any:
        """Return the Qdrant connection manager, or None if unavailable."""
        return self._qdrant_conn

    @property
    def is_initialized(self) -> bool:
        """Whether initialize() has been called."""
        return self._initialized

    def close(self) -> None:
        """Release all pooled connections. Call during app shutdown."""
        if self._neo4j_conn is not None:
            try:
                self._neo4j_conn.close()
                logger.info("Neo4j connection pool closed.")
            except Exception as e:
                logger.error("Error closing Neo4j connection: %s", e)
            self._neo4j_conn = None

        # Qdrant HTTP client doesn't need explicit close,
        # but we clear the reference for safety
        self._qdrant_conn = None
        logger.info("Qdrant connection reference cleared.")

        self._initialized = False
        logger.info("ConnectionPool shutdown complete.")

    def health_check(self) -> dict[str, str]:
        """Return connectivity status for each service."""
        status: dict[str, str] = {}

        # Neo4j
        if self._neo4j_conn is not None:
            try:
                self._neo4j_conn.verify_connectivity()
                status["neo4j"] = "healthy"
            except Exception as e:
                status["neo4j"] = f"unhealthy: {e}"
        else:
            status["neo4j"] = "not_initialized"

        # Qdrant
        if self._qdrant_conn is not None:
            try:
                # QdrantClient has a get_collections method we can use as health probe
                self._qdrant_conn.client.get_collections()
                status["qdrant"] = "healthy"
            except Exception as e:
                status["qdrant"] = f"unhealthy: {e}"
        else:
            status["qdrant"] = "not_initialized"

        return status
