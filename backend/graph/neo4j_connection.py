"""Neo4j connection pool management for the Knowledge Graph layer."""

from __future__ import annotations
from typing import Any

import neo4j

from config.settings import Neo4jSettings


class Neo4jConnectionManager:
    """Manages the lifecycle of a Neo4j driver connection pool.

    Wraps the official neo4j Python driver, providing a single entry point
    for obtaining sessions. Designed for use as a long-lived singleton
    within the application process.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: neo4j.Driver = neo4j.GraphDatabase.driver(
            uri, auth=(user, password)
        )
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize required database schemas such as full-text indices."""
        cypher = (
            "CREATE FULLTEXT INDEX entity_names IF NOT EXISTS "
            "FOR (n:Asset|Component|Person|Location|Date|Parameter|FailureType|Regulation|Event|Entity) "
            "ON EACH [n.canonical_name]"
        )
        try:
            with self._driver.session() as session:
                session.run(cypher)
        except Exception as e:
            # Log error but don't crash, the index might already exist or DB might be starting
            pass

    @classmethod
    def from_settings(cls, settings: Neo4jSettings) -> Neo4jConnectionManager:
        """Create a connection manager from application settings."""
        return cls(uri=settings.uri, user=settings.user, password=settings.password)

    @property
    def driver(self) -> neo4j.Driver:
        """Return the underlying Neo4j driver for session creation."""
        return self._driver

    def verify_connectivity(self) -> None:
        """Verify that the driver can reach the Neo4j server."""
        self._driver.verify_connectivity()

    def close(self) -> None:
        """Close the driver and release all pooled connections."""
        self._driver.close()
