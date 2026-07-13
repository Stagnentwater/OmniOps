"""Unit tests for the Knowledge Graph layer.

Tests use an InMemoryGraphRepository to verify the full GraphRepository
contract, idempotency, MERGE semantics, and evidence lineage preservation
without requiring a live Neo4j instance.
"""

import unittest
from collections import defaultdict
from typing import Any

from graph.repository import GraphRepository
from graph.query_service import GraphQueryService
from graph.neo4j_repository import ENTITY_TYPE_TO_LABEL, ALLOWED_RELATIONSHIP_TYPES
from ingestion.resolution_models import (
    ResolvedEntity,
    ResolvedKnowledgePackage,
    ResolvedRelationship,
)


# ── In-Memory Test Double ──────────────────────────────────────────────


class InMemoryGraphRepository(GraphRepository):
    """In-memory implementation of GraphRepository for testing.

    Faithfully reproduces MERGE semantics: re-persisting the same entity
    or relationship updates properties without creating duplicates.
    """

    def __init__(self) -> None:
        # Nodes keyed by entity_id
        self._nodes: dict[str, dict[str, Any]] = {}
        # Edges keyed by (source_id, rel_type, target_id)
        self._edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    def persist_knowledge_package(self, package: ResolvedKnowledgePackage) -> None:
        document_id = package.document_id

        # Persist Document node
        self._nodes.setdefault(
            f"doc:{document_id}",
            {"document_id": document_id, "entity_type": "document"},
        )

        for entity in package.resolved_entities:
            label = ENTITY_TYPE_TO_LABEL.get(entity.entity_type, "Entity")
            props: dict[str, Any] = {
                "entity_id": entity.entity_id,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "confidence": entity.confidence,
                "document_id": document_id,
                "occurrences": list(entity.occurrences),
                "label": label,
            }
            props.update(entity.properties)

            # MERGE: update if exists, create if not
            if entity.entity_id in self._nodes:
                self._nodes[entity.entity_id].update(props)
            else:
                self._nodes[entity.entity_id] = props

        for rel in package.resolved_relationships:
            if rel.relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
                continue

            key = (
                rel.source_entity_id,
                rel.relationship_type,
                rel.target_entity_id,
            )
            edge_props: dict[str, Any] = {
                "relationship_id": rel.relationship_id,
                "relationship_type": rel.relationship_type,
                "source_entity_id": rel.source_entity_id,
                "target_entity_id": rel.target_entity_id,
                "confidence": rel.confidence,
                "document_id": document_id,
                "occurrences": list(rel.occurrences),
            }
            edge_props.update(rel.metadata)

            if key in self._edges:
                self._edges[key].update(edge_props)
            else:
                self._edges[key] = edge_props

    def get_entity(self, entity_id: str) -> dict | None:
        return dict(self._nodes[entity_id]) if entity_id in self._nodes else None

    def get_neighbors(
        self,
        entity_id: str,
        relationship_type: str | None = None,
        direction: str = "both",
    ) -> list[dict]:
        neighbors: list[dict] = []
        for (src, rel_type, tgt), edge_props in self._edges.items():
            if relationship_type and rel_type != relationship_type:
                continue

            neighbor_id: str | None = None
            if direction in ("outgoing", "both") and src == entity_id:
                neighbor_id = tgt
            if direction in ("incoming", "both") and tgt == entity_id:
                neighbor_id = src

            if neighbor_id and neighbor_id in self._nodes:
                neighbors.append(
                    {
                        "entity": dict(self._nodes[neighbor_id]),
                        "relationship": dict(edge_props),
                    }
                )
        return neighbors

    def traverse(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        max_depth: int = 1,
    ) -> list[dict]:
        visited: set[str] = {entity_id}
        results: list[dict] = []
        frontier: list[tuple[str, int]] = [(entity_id, 0)]

        while frontier:
            current_id, depth = frontier.pop(0)
            if depth >= max_depth:
                continue

            for (src, rel_type, tgt), _ in self._edges.items():
                if relationship_types and rel_type not in relationship_types:
                    continue

                neighbor_id: str | None = None
                if src == current_id and tgt not in visited:
                    neighbor_id = tgt
                elif tgt == current_id and src not in visited:
                    neighbor_id = src

                if neighbor_id and neighbor_id in self._nodes:
                    visited.add(neighbor_id)
                    results.append(
                        {
                            "entity": dict(self._nodes[neighbor_id]),
                            "distance": depth + 1,
                        }
                    )
                    frontier.append((neighbor_id, depth + 1))

        return results

    def expand_subgraph(self, entity_id: str, max_depth: int = 2) -> dict:
        center = self.get_entity(entity_id)
        if center is None:
            return {"center": None, "nodes": [], "edges": []}

        traversal = self.traverse(entity_id, max_depth=max_depth)
        nodes = [center] + [t["entity"] for t in traversal]
        node_ids = {n["entity_id"] for n in nodes}

        edges: list[dict] = []
        for (src, _, tgt), edge_props in self._edges.items():
            if src in node_ids and tgt in node_ids:
                edges.append(dict(edge_props))

        return {"center": center, "nodes": nodes, "edges": edges}

    def search_nodes(self, query: str, limit: int = 5) -> list[dict]:
        results = []
        q = query.lower()
        for node in self._nodes.values():
            if q in node.get("canonical_name", "").lower():
                results.append(dict(node))
                if len(results) >= limit:
                    break
        return results


# ── Test Fixtures ──────────────────────────────────────────────────────


def _make_package(
    document_id: str = "doc-1",
    entities: tuple[ResolvedEntity, ...] = (),
    relationships: tuple[ResolvedRelationship, ...] = (),
) -> ResolvedKnowledgePackage:
    return ResolvedKnowledgePackage(
        document_id=document_id,
        resolved_entities=entities,
        resolved_relationships=relationships,
        metadata={},
    )


def _make_entity(
    entity_id: str = "ent-1",
    entity_type: str = "asset",
    canonical_name: str = "Pump P-301",
    confidence: float = 0.95,
    properties: dict | None = None,
    occurrences: tuple[str, ...] = ("occ-1",),
) -> ResolvedEntity:
    return ResolvedEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        canonical_name=canonical_name,
        confidence=confidence,
        properties=properties or {},
        occurrences=occurrences,
    )


def _make_relationship(
    relationship_id: str = "rel-1",
    relationship_type: str = "HAS_COMPONENT",
    source_entity_id: str = "ent-1",
    target_entity_id: str = "ent-2",
    confidence: float = 0.95,
    occurrences: tuple[str, ...] = ("rocc-1",),
    metadata: dict | None = None,
) -> ResolvedRelationship:
    return ResolvedRelationship(
        relationship_id=relationship_id,
        relationship_type=relationship_type,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        confidence=confidence,
        occurrences=occurrences,
        metadata=metadata or {},
    )


# ── Tests ──────────────────────────────────────────────────────────────


class TestEntityTypeLabelMapping(unittest.TestCase):
    """Verify the controlled entity_type → Neo4j label vocabulary."""

    def test_all_pipeline_types_mapped(self):
        expected = {
            "asset", "component", "person", "location",
            "date", "parameter", "failure_type", "regulation", "event",
        }
        self.assertEqual(set(ENTITY_TYPE_TO_LABEL.keys()), expected)

    def test_labels_are_pascal_case(self):
        for label in ENTITY_TYPE_TO_LABEL.values():
            self.assertTrue(
                label[0].isupper(),
                f"Label '{label}' should start with uppercase",
            )


class TestAllowedRelationshipTypes(unittest.TestCase):
    def test_all_extraction_types_allowed(self):
        expected = {
            "HAS_COMPONENT", "CONNECTED_TO", "MAINTAINED_BY", "LOCATED_IN",
            "INSPECTED_BY", "CAUSES", "REFERENCES", "SIMILAR_TO",
        }
        self.assertEqual(ALLOWED_RELATIONSHIP_TYPES, expected)


class TestGraphRepositoryPersistence(unittest.TestCase):
    """Test write operations through the InMemoryGraphRepository."""

    def setUp(self):
        self.repo = InMemoryGraphRepository()

    def test_persist_single_entity(self):
        entity = _make_entity()
        pkg = _make_package(entities=(entity,))
        self.repo.persist_knowledge_package(pkg)

        node = self.repo.get_entity("ent-1")
        self.assertIsNotNone(node)
        self.assertEqual(node["canonical_name"], "Pump P-301")
        self.assertEqual(node["entity_type"], "asset")
        self.assertEqual(node["confidence"], 0.95)
        self.assertEqual(node["document_id"], "doc-1")
        self.assertEqual(node["occurrences"], ["occ-1"])

    def test_persist_entity_with_properties(self):
        entity = _make_entity(properties={"asset_type": "Pump", "tag": "P-301"})
        pkg = _make_package(entities=(entity,))
        self.repo.persist_knowledge_package(pkg)

        node = self.repo.get_entity("ent-1")
        self.assertEqual(node["asset_type"], "Pump")
        self.assertEqual(node["tag"], "P-301")

    def test_persist_relationship(self):
        e1 = _make_entity(entity_id="ent-1", canonical_name="Pump P-301")
        e2 = _make_entity(
            entity_id="ent-2", entity_type="component", canonical_name="Bearing"
        )
        rel = _make_relationship()
        pkg = _make_package(entities=(e1, e2), relationships=(rel,))
        self.repo.persist_knowledge_package(pkg)

        neighbors = self.repo.get_neighbors("ent-1", direction="outgoing")
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(neighbors[0]["entity"]["canonical_name"], "Bearing")
        self.assertEqual(
            neighbors[0]["relationship"]["relationship_type"], "HAS_COMPONENT"
        )

    def test_unknown_relationship_type_skipped(self):
        e1 = _make_entity(entity_id="ent-1")
        e2 = _make_entity(entity_id="ent-2")
        rel = _make_relationship(relationship_type="UNKNOWN_TYPE")
        pkg = _make_package(entities=(e1, e2), relationships=(rel,))
        self.repo.persist_knowledge_package(pkg)

        neighbors = self.repo.get_neighbors("ent-1")
        self.assertEqual(len(neighbors), 0)

    def test_document_node_created(self):
        pkg = _make_package(document_id="doc-42")
        self.repo.persist_knowledge_package(pkg)
        doc_node = self.repo.get_entity("doc:doc-42")
        self.assertIsNotNone(doc_node)
        self.assertEqual(doc_node["document_id"], "doc-42")


class TestIdempotency(unittest.TestCase):
    """Verify MERGE semantics: re-persisting produces identical state."""

    def setUp(self):
        self.repo = InMemoryGraphRepository()

    def test_entity_idempotent(self):
        entity = _make_entity()
        pkg = _make_package(entities=(entity,))
        self.repo.persist_knowledge_package(pkg)
        self.repo.persist_knowledge_package(pkg)

        # Only one node should exist
        count = sum(
            1 for v in self.repo._nodes.values()
            if v.get("entity_id") == "ent-1"
        )
        self.assertEqual(count, 1)

    def test_relationship_idempotent(self):
        e1 = _make_entity(entity_id="ent-1")
        e2 = _make_entity(entity_id="ent-2", entity_type="component")
        rel = _make_relationship()
        pkg = _make_package(entities=(e1, e2), relationships=(rel,))
        self.repo.persist_knowledge_package(pkg)
        self.repo.persist_knowledge_package(pkg)

        # Only one edge for this triple should exist
        edge_count = sum(
            1 for k in self.repo._edges
            if k == ("ent-1", "HAS_COMPONENT", "ent-2")
        )
        self.assertEqual(edge_count, 1)

    def test_property_update_on_rewrite(self):
        entity_v1 = _make_entity(confidence=0.80)
        pkg_v1 = _make_package(entities=(entity_v1,))
        self.repo.persist_knowledge_package(pkg_v1)

        entity_v2 = _make_entity(confidence=0.95)
        pkg_v2 = _make_package(entities=(entity_v2,))
        self.repo.persist_knowledge_package(pkg_v2)

        node = self.repo.get_entity("ent-1")
        self.assertEqual(node["confidence"], 0.95)


class TestEvidenceLineage(unittest.TestCase):
    """Verify that evidence fields are preserved through persistence."""

    def setUp(self):
        self.repo = InMemoryGraphRepository()

    def test_entity_preserves_occurrences(self):
        entity = _make_entity(occurrences=("occ-a", "occ-b", "occ-c"))
        pkg = _make_package(entities=(entity,))
        self.repo.persist_knowledge_package(pkg)

        node = self.repo.get_entity("ent-1")
        self.assertEqual(set(node["occurrences"]), {"occ-a", "occ-b", "occ-c"})

    def test_entity_preserves_document_id(self):
        entity = _make_entity()
        pkg = _make_package(document_id="doc-99", entities=(entity,))
        self.repo.persist_knowledge_package(pkg)

        node = self.repo.get_entity("ent-1")
        self.assertEqual(node["document_id"], "doc-99")

    def test_relationship_preserves_evidence(self):
        e1 = _make_entity(entity_id="ent-1")
        e2 = _make_entity(entity_id="ent-2", entity_type="component")
        rel = _make_relationship(
            occurrences=("rocc-x", "rocc-y"),
        )
        pkg = _make_package(
            document_id="doc-77",
            entities=(e1, e2),
            relationships=(rel,),
        )
        self.repo.persist_knowledge_package(pkg)

        neighbors = self.repo.get_neighbors("ent-1", direction="outgoing")
        edge = neighbors[0]["relationship"]
        self.assertEqual(edge["document_id"], "doc-77")
        self.assertEqual(set(edge["occurrences"]), {"rocc-x", "rocc-y"})


class TestGetNeighbors(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryGraphRepository()
        e1 = _make_entity(entity_id="ent-1", canonical_name="Pump P-301")
        e2 = _make_entity(
            entity_id="ent-2", entity_type="component", canonical_name="Bearing"
        )
        e3 = _make_entity(
            entity_id="ent-3", entity_type="person", canonical_name="Smith"
        )
        r1 = _make_relationship(
            relationship_id="r1", source_entity_id="ent-1", target_entity_id="ent-2"
        )
        r2 = _make_relationship(
            relationship_id="r2",
            relationship_type="MAINTAINED_BY",
            source_entity_id="ent-1",
            target_entity_id="ent-3",
        )
        pkg = _make_package(entities=(e1, e2, e3), relationships=(r1, r2))
        self.repo.persist_knowledge_package(pkg)

    def test_all_neighbors(self):
        result = self.repo.get_neighbors("ent-1")
        self.assertEqual(len(result), 2)

    def test_filter_by_type(self):
        result = self.repo.get_neighbors(
            "ent-1", relationship_type="HAS_COMPONENT"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["entity"]["canonical_name"], "Bearing")

    def test_direction_outgoing(self):
        result = self.repo.get_neighbors("ent-1", direction="outgoing")
        self.assertEqual(len(result), 2)

    def test_direction_incoming(self):
        result = self.repo.get_neighbors("ent-2", direction="incoming")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["entity"]["canonical_name"], "Pump P-301")

    def test_no_neighbors(self):
        result = self.repo.get_neighbors("nonexistent-id")
        self.assertEqual(len(result), 0)


class TestTraverse(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryGraphRepository()
        # Chain: ent-1 --HAS_COMPONENT--> ent-2 --CAUSES--> ent-3
        e1 = _make_entity(entity_id="ent-1")
        e2 = _make_entity(entity_id="ent-2", entity_type="component")
        e3 = _make_entity(entity_id="ent-3", entity_type="failure_type")
        r1 = _make_relationship(
            relationship_id="r1", source_entity_id="ent-1", target_entity_id="ent-2"
        )
        r2 = _make_relationship(
            relationship_id="r2",
            relationship_type="CAUSES",
            source_entity_id="ent-2",
            target_entity_id="ent-3",
        )
        pkg = _make_package(entities=(e1, e2, e3), relationships=(r1, r2))
        self.repo.persist_knowledge_package(pkg)

    def test_traverse_depth_1(self):
        result = self.repo.traverse("ent-1", max_depth=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["distance"], 1)

    def test_traverse_depth_2(self):
        result = self.repo.traverse("ent-1", max_depth=2)
        self.assertEqual(len(result), 2)
        distances = {r["entity"]["entity_id"]: r["distance"] for r in result}
        self.assertEqual(distances["ent-2"], 1)
        self.assertEqual(distances["ent-3"], 2)

    def test_traverse_with_type_filter(self):
        result = self.repo.traverse(
            "ent-1", relationship_types=["HAS_COMPONENT"], max_depth=2
        )
        # Only follows HAS_COMPONENT, so only reaches ent-2
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["entity"]["entity_id"], "ent-2")


class TestExpandSubgraph(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryGraphRepository()
        e1 = _make_entity(entity_id="ent-1")
        e2 = _make_entity(entity_id="ent-2", entity_type="component")
        r1 = _make_relationship(
            relationship_id="r1", source_entity_id="ent-1", target_entity_id="ent-2"
        )
        pkg = _make_package(entities=(e1, e2), relationships=(r1,))
        self.repo.persist_knowledge_package(pkg)

    def test_expand_returns_structure(self):
        result = self.repo.expand_subgraph("ent-1", max_depth=1)
        self.assertIsNotNone(result["center"])
        self.assertEqual(result["center"]["entity_id"], "ent-1")
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(len(result["edges"]), 1)

    def test_expand_nonexistent_entity(self):
        result = self.repo.expand_subgraph("no-such-entity")
        self.assertIsNone(result["center"])
        self.assertEqual(len(result["nodes"]), 0)
        self.assertEqual(len(result["edges"]), 0)


class TestQueryService(unittest.TestCase):
    """Verify that GraphQueryService delegates correctly to the repository."""

    def setUp(self):
        self.repo = InMemoryGraphRepository()
        e1 = _make_entity(entity_id="ent-1")
        e2 = _make_entity(entity_id="ent-2", entity_type="component")
        r1 = _make_relationship(
            source_entity_id="ent-1", target_entity_id="ent-2"
        )
        pkg = _make_package(entities=(e1, e2), relationships=(r1,))
        self.repo.persist_knowledge_package(pkg)
        self.service = GraphQueryService(self.repo)

    def test_get_entity(self):
        result = self.service.get_entity("ent-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["canonical_name"], "Pump P-301")

    def test_get_entity_not_found(self):
        result = self.service.get_entity("nonexistent")
        self.assertIsNone(result)

    def test_get_neighbors(self):
        result = self.service.get_neighbors("ent-1")
        self.assertEqual(len(result), 1)

    def test_traverse(self):
        result = self.service.traverse("ent-1", max_depth=1)
        self.assertEqual(len(result), 1)

    def test_expand_subgraph(self):
        result = self.service.expand_subgraph("ent-1", max_depth=1)
        self.assertIsNotNone(result["center"])


if __name__ == "__main__":
    unittest.main()
