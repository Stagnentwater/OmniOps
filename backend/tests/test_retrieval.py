"""Unit tests for the Retrieval Layer."""

import unittest

from retrieval.service import RetrievalService
from retrieval.retrieval_models import RetrievalContext
from vector.repository import SearchResult, VectorRepository
from vector.embedding_provider import EmbeddingProvider
from graph.query_service import GraphQueryService
from graph.repository import GraphRepository


class MockEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return 3

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        # Mock deterministic embedding based on length
        return [[float(len(t))] * 3 for t in texts]


class MockVectorRepository(VectorRepository):
    def __init__(self):
        self.upserted = []
        
    def upsert_chunks(self, chunks, embeddings) -> None:
        self.upserted.append((chunks, embeddings))

    def search(
        self, query_embedding: list[float], limit: int = 5, document_id: str | None = None
    ) -> list[SearchResult]:
        # Return deterministic mock results
        return [
            SearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="semantic match 1",
                score=0.95,
                page_index=1,
                section="Intro",
                metadata={"confidence": 0.9}
            ),
            SearchResult(
                chunk_id="chunk-1", # Duplicate to test deduplication
                document_id="doc-1",
                text="semantic match 1",
                score=0.95,
                page_index=1,
                section="Intro",
                metadata={"confidence": 0.9}
            ),
            SearchResult(
                chunk_id="chunk-2",
                document_id="doc-2",
                text="semantic match 2",
                score=0.85,
                page_index=5,
                section=None,
                metadata={}
            )
        ][:limit]


class MockGraphRepository(GraphRepository):
    def persist_knowledge_package(self, package) -> None:
        pass
        
    def get_entity(self, entity_id: str) -> dict | None:
        return None
        
    def get_neighbors(self, entity_id: str, relationship_type=None, direction="both") -> list[dict]:
        return []
        
    def traverse(self, entity_id: str, relationship_types=None, max_depth=1) -> list[dict]:
        return []
        
    def search_nodes(self, query: str, limit: int = 5) -> list[dict]:
        # Mock search based on query
        if "pump" in query.lower():
            return [
                {
                    "entity_id": "ent-1",
                    "entity_type": "Asset",
                    "canonical_name": "Main Pump",
                    "confidence": 0.99
                }
            ]
        return []
        
    def expand_subgraph(self, entity_id: str, max_depth: int = 2) -> dict:
        if entity_id == "ent-1":
            return {
                "center": {"entity_id": "ent-1", "canonical_name": "Main Pump"},
                "nodes": [
                    {"entity_id": "ent-2", "entity_type": "Location", "canonical_name": "Sector 4"}
                ],
                "edges": [
                    {
                        "source_entity_id": "ent-1",
                        "target_entity_id": "ent-2",
                        "relationship_type": "LOCATED_IN",
                        "confidence": 0.8
                    }
                ]
            }
        return {"center": None, "nodes": [], "edges": []}


class TestRetrievalService(unittest.TestCase):
    def setUp(self):
        self.vector_repo = MockVectorRepository()
        self.graph_repo = MockGraphRepository()
        self.graph_service = GraphQueryService(self.graph_repo)
        self.embedding_provider = MockEmbeddingProvider()
        
        self.service = RetrievalService(
            vector_repo=self.vector_repo,
            graph_service=self.graph_service,
            embedding_provider=self.embedding_provider
        )

    def test_retrieve_merges_and_deduplicates(self):
        query = "Where is the main pump located?"
        
        context: RetrievalContext = self.service.retrieve(query, limit=5)
        
        # 1. Check Chunks (deduplication from 3 items -> 2 unique)
        self.assertEqual(len(context.chunks), 2)
        self.assertEqual(context.chunks[0].chunk_id, "chunk-1")
        self.assertEqual(context.chunks[0].score, 0.95)
        self.assertEqual(context.chunks[1].chunk_id, "chunk-2")
        
        # 2. Check Entities (Center + 1 connected node)
        self.assertEqual(len(context.entities), 2)
        entity_ids = {e.entity_id for e in context.entities}
        self.assertIn("ent-1", entity_ids)
        self.assertIn("ent-2", entity_ids)
        
        # 3. Check Relationships
        self.assertEqual(len(context.relationships), 1)
        rel = context.relationships[0]
        self.assertEqual(rel.source_id, "ent-1")
        self.assertEqual(rel.target_id, "ent-2")
        self.assertEqual(rel.relationship_type, "LOCATED_IN")
        
    def test_retrieve_empty_query(self):
        # Empty string or a string with no graph match
        context = self.service.retrieve("random text without trigger word", limit=5)
        
        # Vector repo still returns dummy data
        self.assertEqual(len(context.chunks), 2)
        # Graph repo should return empty based on our mock
        self.assertEqual(len(context.entities), 0)
        self.assertEqual(len(context.relationships), 0)

if __name__ == "__main__":
    unittest.main()
