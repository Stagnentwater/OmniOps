"""Unit tests for the Vector Pipeline layer (Sprint 8)."""

import unittest
from typing import Any

from ingestion.chunk_models import Chunk, ChunkCollection
from vector.embedding_provider import EmbeddingProvider
from vector.repository import SearchResult, VectorRepository


class FakeEmbeddingProvider(EmbeddingProvider):
    """Fake embedding provider that generates deterministic dummy vectors."""

    def __init__(self, dimension: int = 3):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        # Generate deterministic mock vectors based on text length
        embeddings = []
        for text in texts:
            val = float(len(text))
            # Just repeat the value to fill the dimension
            embeddings.append([val] * self._dimension)
        return embeddings


class InMemoryVectorRepository(VectorRepository):
    """In-memory implementation of VectorRepository to test contracts and idempotency."""

    def __init__(self):
        # Keyed by chunk_id
        self._store: dict[str, dict[str, Any]] = {}

    def upsert_chunks(self, chunks: ChunkCollection, embeddings: list[list[float]]) -> None:
        if len(chunks.chunks) != len(embeddings):
            raise ValueError("Mismatch")

        for chunk, embedding in zip(chunks.chunks, embeddings):
            payload = {
                "document_id": chunk.document_id,
                "text": chunk.text,
                "page_index": chunk.page_index,
                "section": chunk.section,
                "chunk_index": chunk.chunk_index,
            }
            # Add metadata
            for k, v in chunk.metadata.items():
                if k not in payload:
                    payload[k] = v

            # Idempotent write (overwrite if exists)
            self._store[chunk.chunk_id] = {
                "vector": embedding,
                "payload": payload,
            }

    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        
        results = []
        for chunk_id, data in self._store.items():
            payload = data["payload"]
            
            if document_id and payload.get("document_id") != document_id:
                continue
                
            # Dummy score calculation (negative distance)
            score = -sum((a - b) ** 2 for a, b in zip(data["vector"], query_embedding))
            
            # Construct SearchResult
            meta = dict(payload)
            d_id = meta.pop("document_id")
            text = meta.pop("text")
            page_index = meta.pop("page_index")
            section = meta.pop("section", None)
            meta.pop("chunk_index", None)
            
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=d_id,
                    text=text,
                    score=score,
                    page_index=page_index,
                    section=section,
                    metadata=meta,
                )
            )
            
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class TestVectorPipeline(unittest.TestCase):

    def setUp(self):
        self.provider = FakeEmbeddingProvider(dimension=4)
        self.repo = InMemoryVectorRepository()

        self.chunk1 = Chunk(
            chunk_id="chk-1",
            document_id="doc-A",
            chunk_index=0,
            text="The quick brown fox",
            page_index=1,
            section="Intro",
            metadata={"source": "manual"}
        )
        self.chunk2 = Chunk(
            chunk_id="chk-2",
            document_id="doc-A",
            chunk_index=1,
            text="jumps over the lazy dog",
            page_index=1,
            section="Body",
            metadata={"source": "manual", "importance": "high"}
        )
        self.chunk3 = Chunk(
            chunk_id="chk-3",
            document_id="doc-B",
            chunk_index=0,
            text="short",
            page_index=5,
            section=None,
            metadata={}
        )
        
        self.collection_a = ChunkCollection(
            document_id="doc-A",
            chunks=(self.chunk1, self.chunk2),
            chunk_count=2
        )
        self.collection_b = ChunkCollection(
            document_id="doc-B",
            chunks=(self.chunk3,),
            chunk_count=1
        )

    def test_embedding_provider(self):
        texts = ["hello", "world!"]
        embeddings = self.provider.generate_embeddings(texts)
        self.assertEqual(len(embeddings), 2)
        self.assertEqual(len(embeddings[0]), 4)
        # Check deterministic values based on text length
        self.assertEqual(embeddings[0], [5.0, 5.0, 5.0, 5.0])
        self.assertEqual(embeddings[1], [6.0, 6.0, 6.0, 6.0])

    def test_upsert_and_payload_preservation(self):
        embeddings = self.provider.generate_embeddings([c.text for c in self.collection_a.chunks])
        self.repo.upsert_chunks(self.collection_a, embeddings)
        
        # Verify it's in the repo
        self.assertIn("chk-1", self.repo._store)
        self.assertIn("chk-2", self.repo._store)
        
        # Verify payload structure
        payload2 = self.repo._store["chk-2"]["payload"]
        self.assertEqual(payload2["document_id"], "doc-A")
        self.assertEqual(payload2["text"], "jumps over the lazy dog")
        self.assertEqual(payload2["section"], "Body")
        self.assertEqual(payload2["source"], "manual")
        self.assertEqual(payload2["importance"], "high")

    def test_idempotent_upserts(self):
        embeddings = self.provider.generate_embeddings([c.text for c in self.collection_a.chunks])
        
        # Upsert first time
        self.repo.upsert_chunks(self.collection_a, embeddings)
        self.assertEqual(len(self.repo._store), 2)
        
        # Upsert second time (idempotent)
        self.repo.upsert_chunks(self.collection_a, embeddings)
        self.assertEqual(len(self.repo._store), 2)  # Should not increase
        
    def test_search_and_ranking(self):
        embeddings_a = self.provider.generate_embeddings([c.text for c in self.collection_a.chunks])
        embeddings_b = self.provider.generate_embeddings([c.text for c in self.collection_b.chunks])
        self.repo.upsert_chunks(self.collection_a, embeddings_a)
        self.repo.upsert_chunks(self.collection_b, embeddings_b)
        
        # Query with embedding matching length of chunk2's text (length 23)
        query_emb = [23.0, 23.0, 23.0, 23.0]
        results = self.repo.search(query_emb, limit=10)
        
        # Ranked by dummy score (closest match first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].chunk_id, "chk-2")
        self.assertEqual(results[1].chunk_id, "chk-1")
        self.assertEqual(results[2].chunk_id, "chk-3")

    def test_search_with_metadata_filter(self):
        embeddings_a = self.provider.generate_embeddings([c.text for c in self.collection_a.chunks])
        embeddings_b = self.provider.generate_embeddings([c.text for c in self.collection_b.chunks])
        self.repo.upsert_chunks(self.collection_a, embeddings_a)
        self.repo.upsert_chunks(self.collection_b, embeddings_b)
        
        # Query matching chunk2 ideally, but filter for doc-B only
        query_emb = [23.0, 23.0, 23.0, 23.0]
        results = self.repo.search(query_emb, limit=10, document_id="doc-B")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, "chk-3")

if __name__ == "__main__":
    unittest.main()
