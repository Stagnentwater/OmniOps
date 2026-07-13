"""Abstract interface for Vector Database persistence and retrieval."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ingestion.chunk_models import ChunkCollection


@dataclass(frozen=True)
class SearchResult:
    """Represents a single semantically matched chunk from the vector database."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    page_index: int
    section: str | None
    metadata: dict[str, Any]


class VectorRepository(ABC):
    """Abstract interface for vector database operations.

    The retrieval and semantic search engines depend exclusively on this
    interface. Write operations consume chunks and their corresponding embeddings,
    persisting them alongside payload metadata.
    """

    @abstractmethod
    def upsert_chunks(self, chunks: ChunkCollection, embeddings: list[list[float]]) -> None:
        """Upsert a collection of chunks and their corresponding embeddings.

        Must guarantee idempotent writes. If a chunk with the same ID is upserted
        again, it must safely overwrite the existing vector and payload.

        Args:
            chunks: The collection of chunks to persist.
            embeddings: Dense vector representations corresponding 1:1 with
                the chunks in the collection.
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        """Perform a semantic search to retrieve the most similar chunks.

        Args:
            query_embedding: The dense vector representation of the query.
            limit: Maximum number of results to return.
            document_id: Optional exact-match filter on the document ID.

        Returns:
            A list of SearchResult objects, ranked by similarity score (descending).
        """
        pass
