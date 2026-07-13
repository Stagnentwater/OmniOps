"""Graph query service providing read-only access to the Knowledge Graph.

This service is strictly a graph access layer. It delegates all operations
to the abstract GraphRepository interface and does NOT perform:
- GraphRAG
- vector search combination
- result ranking
- prompt preparation
- LLM calls
- retrieval logic
"""

from __future__ import annotations

from graph.repository import GraphRepository


class GraphQueryService:
    """Read-only query interface for the Knowledge Graph.

    Depends only on the abstract GraphRepository interface, never on a
    concrete Neo4j implementation. Downstream retrieval and reasoning
    layers consume this service for structured graph access.
    """

    def __init__(self, repository: GraphRepository) -> None:
        self._repository = repository

    def get_entity(self, entity_id: str) -> dict | None:
        """Retrieve a single entity by its canonical ID.

        Args:
            entity_id: Deterministic canonical hash of the entity.

        Returns:
            A dict of all node properties, or None if not found.
        """
        return self._repository.get_entity(entity_id)

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

        Returns:
            A list of dicts, each containing 'entity' and 'relationship' keys.
        """
        return self._repository.get_neighbors(
            entity_id, relationship_type=relationship_type, direction=direction
        )

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
            max_depth: Maximum number of hops.

        Returns:
            A list of dicts with 'entity' properties and 'distance' from start.
        """
        return self._repository.traverse(
            entity_id, relationship_types=relationship_types, max_depth=max_depth
        )

    def expand_subgraph(self, entity_id: str, max_depth: int = 2) -> dict:
        """Expand the full subgraph around an entity.

        Args:
            entity_id: Center entity canonical ID.
            max_depth: Maximum expansion depth.

        Returns:
            A dict with 'center', 'nodes', and 'edges' keys.
        """
        return self._repository.expand_subgraph(entity_id, max_depth=max_depth)
