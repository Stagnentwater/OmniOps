"""Abstract interface for Knowledge Graph persistence and query operations."""

from __future__ import annotations
from abc import ABC, abstractmethod

from ingestion.resolution_models import ResolvedKnowledgePackage


class GraphRepository(ABC):
    """Abstract interface for graph database operations.

    All higher layers (orchestrators, query services, retrieval engines)
    must depend on this interface rather than any concrete implementation.

    Write operations consume ResolvedKnowledgePackage objects produced by
    the Knowledge Resolution stage. Read operations provide graph traversal
    primitives for downstream query and retrieval services.
    """

    # ── Write Operations ──────────────────────────────────────────────

    @abstractmethod
    def persist_knowledge_package(self, package: ResolvedKnowledgePackage) -> None:
        """Persist all resolved entities and relationships from a knowledge package.

        Must be idempotent: re-persisting the same package produces
        identical graph state without creating duplicate nodes or edges.
        """

    # ── Read Operations ───────────────────────────────────────────────

    @abstractmethod
    def get_entity(self, entity_id: str) -> dict | None:
        """Retrieve a single entity node by its canonical ID.

        Returns a dict of all node properties, or None if not found.
        """

    @abstractmethod
    def get_neighbors(
        self,
        entity_id: str,
        relationship_type: str | None = None,
        direction: str = "both",
    ) -> list[dict]:
        """Retrieve immediate neighbors of an entity.

        Args:
            entity_id: Canonical ID of the center entity.
            relationship_type: Optional filter for a specific relationship type.
            direction: One of 'outgoing', 'incoming', or 'both'.

        Returns a list of dicts, each containing 'entity' (node properties)
        and 'relationship' (edge properties including type).
        """

    @abstractmethod
    def traverse(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        max_depth: int = 1,
    ) -> list[dict]:
        """Traverse the graph from an entity up to max_depth hops.

        Args:
            entity_id: Starting entity canonical ID.
            relationship_types: Optional list of relationship types to follow.
            max_depth: Maximum number of hops (1-indexed).

        Returns a list of dicts representing discovered entities with
        their distance from the starting node.
        """

    @abstractmethod
    def expand_subgraph(self, entity_id: str, max_depth: int = 2) -> dict:
        """Expand the full subgraph around an entity up to max_depth.

        Returns a dict with:
            'center': The center entity properties.
            'nodes': List of all entity property dicts in the subgraph.
            'edges': List of all relationship property dicts in the subgraph.
        """
