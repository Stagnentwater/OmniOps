"""Neo4j implementation of the GraphRepository interface."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

import neo4j

from graph.neo4j_connection import Neo4jConnectionManager
from graph.repository import GraphRepository
from ingestion.resolution_models import (
    ResolvedEntity,
    ResolvedKnowledgePackage,
    ResolvedRelationship,
)


# Mapping from pipeline entity_type strings to Neo4j node labels.
# Controlled vocabulary — only these labels are ever written.
ENTITY_TYPE_TO_LABEL: dict[str, str] = {
    "asset": "Asset",
    "component": "Component",
    "person": "Person",
    "location": "Location",
    "date": "Date",
    "parameter": "Parameter",
    "failure_type": "FailureType",
    "regulation": "Regulation",
    "event": "Event",
}

# Controlled set of allowed relationship types from the extraction layer.
ALLOWED_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "HAS_COMPONENT",
        "CONNECTED_TO",
        "MAINTAINED_BY",
        "LOCATED_IN",
        "INSPECTED_BY",
        "CAUSES",
        "REFERENCES",
        "SIMILAR_TO",
    }
)


class Neo4jGraphRepository(GraphRepository):
    """Concrete Neo4j implementation of the GraphRepository interface.

    Uses MERGE semantics throughout to guarantee idempotent writes.
    Every node is MERGEd on its deterministic ``entity_id`` property.
    Every relationship is MERGEd on the ``(source, type, target)`` triple.
    """

    def __init__(self, connection_manager: Neo4jConnectionManager) -> None:
        self._driver = connection_manager.driver

    # ── Write Operations ──────────────────────────────────────────────

    def persist_knowledge_package(self, package: ResolvedKnowledgePackage) -> None:
        """Persist all entities and relationships in a single transaction."""
        with self._driver.session() as session:
            session.execute_write(
                self._persist_package_tx, package
            )

    @staticmethod
    def _persist_package_tx(
        tx: neo4j.ManagedTransaction,
        package: ResolvedKnowledgePackage,
    ) -> None:
        """Transaction function that writes the entire package atomically."""
        document_id = package.document_id
        now = datetime.now(timezone.utc).isoformat()

        # 1. Create/update the source Document node
        tx.run(
            "MERGE (d:Document {document_id: $document_id}) "
            "SET d.updated_at = $now",
            document_id=document_id,
            now=now,
        )

        # 2. Persist resolved entities
        for entity in package.resolved_entities:
            _persist_entity(tx, entity, document_id, now)

        # 3. Persist resolved relationships
        for relationship in package.resolved_relationships:
            _persist_relationship(tx, relationship, document_id, now)

    def delete_document(self, document_id: str) -> None:
        """Delete all entities and relationships associated with a document."""
        with self._driver.session() as session:
            session.execute_write(self._delete_document_tx, document_id)
            
    @staticmethod
    def _delete_document_tx(tx: neo4j.ManagedTransaction, document_id: str) -> None:
        """Transaction function to delete a document and its nodes."""
        # 1. Delete all relationships pointing to this document_id
        tx.run(
            "MATCH ()-[r {document_id: $document_id}]->() DELETE r",
            document_id=document_id,
        )
        # 2. Delete all nodes pointing to this document_id
        tx.run(
            "MATCH (n {document_id: $document_id}) DETACH DELETE n",
            document_id=document_id,
        )
        # 3. Delete the Document node itself
        tx.run(
            "MATCH (d:Document {document_id: $document_id}) DETACH DELETE d",
            document_id=document_id,
        )

    # ── Read Operations ───────────────────────────────────────────────

    def get_entity(self, entity_id: str) -> dict | None:
        """Retrieve a single entity by canonical ID."""
        with self._driver.session() as session:
            result = session.execute_read(
                _get_entity_tx, entity_id
            )
        return result

    def get_neighbors(
        self,
        entity_id: str,
        relationship_type: str | None = None,
        direction: str = "both",
    ) -> list[dict]:
        """Retrieve immediate neighbors with optional type and direction filters."""
        with self._driver.session() as session:
            return session.execute_read(
                _get_neighbors_tx, entity_id, relationship_type, direction
            )

    def traverse(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        max_depth: int = 1,
    ) -> list[dict]:
        """Traverse from an entity up to max_depth hops."""
        with self._driver.session() as session:
            return session.execute_read(
                _traverse_tx, entity_id, relationship_types, max_depth
            )

    def expand_subgraph(self, entity_id: str, max_depth: int = 2) -> dict:
        """Expand the full subgraph around an entity."""
        with self._driver.session() as session:
            return session.execute_read(
                _expand_subgraph_tx, entity_id, max_depth
            )

    def search_nodes(self, query: str, limit: int = 5) -> list[dict]:
        """Search graph nodes using text indexing (or simple keyword match)."""
        with self._driver.session() as session:
            return session.execute_read(
                _search_nodes_tx, query, limit
            )

    def get_full_graph(self, limit: int = 150) -> dict:
        """Fetch a broad overview of the knowledge graph for visualization."""
        with self._driver.session() as session:
            return session.execute_read(
                _get_full_graph_tx, limit
            )


# ── Private Transaction Functions ─────────────────────────────────────


def _persist_entity(
    tx: neo4j.ManagedTransaction,
    entity: ResolvedEntity,
    document_id: str,
    now: str,
) -> None:
    """MERGE a single entity node with its properties."""
    label = ENTITY_TYPE_TO_LABEL.get(entity.entity_type, "Entity")

    # Build safe property map for SET n += $props
    props: dict[str, Any] = {
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "confidence": entity.confidence,
        "document_id": document_id,
        "occurrences": list(entity.occurrences),
        "updated_at": now,
    }
    # Merge type-specific properties from the resolved attributes
    for key, value in entity.properties.items():
        props[key] = value

    query = (
        f"MERGE (n:{label} {{entity_id: $entity_id}}) "
        f"SET n += $props"
    )
    tx.run(query, entity_id=entity.entity_id, props=props)


def _persist_relationship(
    tx: neo4j.ManagedTransaction,
    relationship: ResolvedRelationship,
    document_id: str,
    now: str,
) -> None:
    """MERGE a single relationship between two already-persisted entity nodes."""
    # Clean up relationship type to be a valid Neo4j relationship type
    rel_type = relationship.relationship_type.upper().replace(" ", "_").replace("-", "_")

    props: dict[str, Any] = {
        "relationship_id": relationship.relationship_id,
        "confidence": relationship.confidence,
        "document_id": document_id,
        "occurrences": list(relationship.occurrences),
        "updated_at": now,
    }
    for key, value in relationship.metadata.items():
        props[key] = value

    query = (
        f"MATCH (src {{entity_id: $source_id}}) "
        f"MATCH (tgt {{entity_id: $target_id}}) "
        f"MERGE (src)-[r:{rel_type}]->(tgt) "
        f"SET r += $props"
    )
    tx.run(
        query,
        source_id=relationship.source_entity_id,
        target_id=relationship.target_entity_id,
        props=props,
    )


def _get_entity_tx(
    tx: neo4j.ManagedTransaction,
    entity_id: str,
) -> dict | None:
    """Read transaction: fetch a single entity node."""
    result = tx.run(
        "MATCH (n {entity_id: $entity_id}) "
        "RETURN properties(n) AS props",
        entity_id=entity_id,
    )
    record = result.single()
    if record is None:
        return None
    return dict(record["props"])


def _get_neighbors_tx(
    tx: neo4j.ManagedTransaction,
    entity_id: str,
    relationship_type: str | None,
    direction: str,
) -> list[dict]:
    """Read transaction: fetch immediate neighbors."""
    # Build the directional pattern
    if direction == "outgoing":
        pattern = "(n {entity_id: $entity_id})-[r]->(m)"
    elif direction == "incoming":
        pattern = "(n {entity_id: $entity_id})<-[r]-(m)"
    else:
        pattern = "(n {entity_id: $entity_id})-[r]-(m)"

    if relationship_type:
        query = (
            f"MATCH {pattern} "
            f"WHERE type(r) = $rel_type "
            f"RETURN properties(m) AS entity, properties(r) AS relationship, type(r) AS relationship_type"
        )
        result = tx.run(query, entity_id=entity_id, rel_type=relationship_type)
    else:
        query = (
            f"MATCH {pattern} "
            f"RETURN properties(m) AS entity, properties(r) AS relationship, type(r) AS relationship_type"
        )
        result = tx.run(query, entity_id=entity_id)

    neighbors: list[dict] = []
    for record in result:
        rel_props = dict(record["relationship"])
        rel_props["relationship_type"] = record["relationship_type"]
        neighbors.append(
            {
                "entity": dict(record["entity"]),
                "relationship": rel_props,
            }
        )
    return neighbors


def _traverse_tx(
    tx: neo4j.ManagedTransaction,
    entity_id: str,
    relationship_types: list[str] | None,
    max_depth: int,
) -> list[dict]:
    """Read transaction: traverse up to max_depth hops."""
    depth = max(1, min(max_depth, 10))  # Clamp depth to [1, 10]

    if relationship_types:
        rel_filter = "|".join(f"`{rt}`" for rt in relationship_types)
        path_pattern = f"[*1..{depth}]"
        query = (
            f"MATCH (start {{entity_id: $entity_id}}) "
            f"MATCH path = (start)-[:{rel_filter}*1..{depth}]-(target) "
            f"RETURN DISTINCT properties(target) AS entity, length(path) AS distance"
        )
    else:
        query = (
            f"MATCH (start {{entity_id: $entity_id}}) "
            f"MATCH path = (start)-[*1..{depth}]-(target) "
            f"RETURN DISTINCT properties(target) AS entity, length(path) AS distance"
        )

    result = tx.run(query, entity_id=entity_id)
    return [
        {"entity": dict(record["entity"]), "distance": record["distance"]}
        for record in result
    ]


def _expand_subgraph_tx(
    tx: neo4j.ManagedTransaction,
    entity_id: str,
    max_depth: int,
) -> dict:
    """Read transaction: expand full subgraph around an entity."""
    depth = max(1, min(max_depth, 10))

    # Get the center node
    center_result = tx.run(
        "MATCH (n {entity_id: $entity_id}) RETURN properties(n) AS props",
        entity_id=entity_id,
    )
    center_record = center_result.single()
    if center_record is None:
        return {"center": None, "nodes": [], "edges": []}

    center = dict(center_record["props"])

    # Get all nodes and edges in the subgraph
    query = (
        f"MATCH (start {{entity_id: $entity_id}}) "
        f"MATCH path = (start)-[*1..{depth}]-(target) "
        f"UNWIND relationships(path) AS r "
        f"WITH COLLECT(DISTINCT target) AS targets, "
        f"     COLLECT(DISTINCT {{rel: r, src: startNode(r), tgt: endNode(r)}}) AS rels "
        f"RETURN targets, rels"
    )
    result = tx.run(query, entity_id=entity_id)
    record = result.single()

    nodes: list[dict] = [center]
    edges: list[dict] = []

    if record is not None:
        for node in record["targets"]:
            node_props = dict(node)
            if node_props.get("entity_id") != entity_id:
                nodes.append(node_props)

        for rel_data in record["rels"]:
            rel = rel_data["rel"]
            src = rel_data["src"]
            tgt = rel_data["tgt"]
            edge_props = dict(rel)
            edge_props["relationship_type"] = rel.type
            edge_props["source_entity_id"] = dict(src).get("entity_id", "")
            edge_props["target_entity_id"] = dict(tgt).get("entity_id", "")
            edges.append(edge_props)

    return {"center": center, "nodes": nodes, "edges": edges}


def _search_nodes_tx(
    tx: neo4j.ManagedTransaction, query: str, limit: int
) -> list[dict]:
    """Read transaction: Search nodes by canonical_name (case-insensitive substring match)."""
    # Simple fuzzy-like search on canonical_name for MVP.
    # In production, use Neo4j Full-Text Search indices.
    cypher = (
        "MATCH (n) "
        "WHERE toLower(n.canonical_name) CONTAINS toLower($search_term) "
        "RETURN properties(n) AS props "
        "LIMIT $limit"
    )
    result = tx.run(cypher, search_term=query, limit=limit)
    return [dict(record["props"]) for record in result]


def _get_full_graph_tx(
    tx: neo4j.ManagedTransaction, limit: int
) -> dict:
    """Read transaction: Fetch a subset of the graph nodes and their relationships."""
    query = (
        "MATCH (n) "
        "WITH n LIMIT $limit "
        "OPTIONAL MATCH (n)-[r]->(m) "
        "WITH COLLECT(DISTINCT n) AS nodes1, COLLECT(DISTINCT m) AS nodes2, "
        "     COLLECT(DISTINCT {rel: r, src: startNode(r), tgt: endNode(r)}) AS rels "
        "RETURN nodes1, nodes2, rels"
    )
    result = tx.run(query, limit=limit)
    record = result.single()

    nodes_dict = {}
    edges = []

    if record is not None:
        for node in record["nodes1"]:
            if node:
                props = dict(node)
                nodes_dict[props.get("entity_id")] = props
                
        for node in record["nodes2"]:
            if node:
                props = dict(node)
                nodes_dict[props.get("entity_id")] = props

        for rel_data in record["rels"]:
            rel = rel_data.get("rel")
            if rel:
                src = rel_data["src"]
                tgt = rel_data["tgt"]
                edge_props = dict(rel)
                edge_props["relationship_type"] = rel.type
                edge_props["source_entity_id"] = dict(src).get("entity_id", "")
                edge_props["target_entity_id"] = dict(tgt).get("entity_id", "")
                edges.append(edge_props)

    return {"nodes": list(nodes_dict.values()), "edges": edges}

