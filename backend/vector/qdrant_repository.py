"""Concrete Qdrant implementation of the VectorRepository interface."""

from __future__ import annotations
import uuid
from typing import Any

from qdrant_client import models

from ingestion.chunk_models import ChunkCollection
from vector.qdrant_connection import QdrantConnectionManager
from vector.repository import SearchResult, VectorRepository


class QdrantVectorRepository(VectorRepository):
    """Qdrant-backed implementation of the VectorRepository interface.

    Handles idempotent upserts and semantic search with metadata filtering.
    """

    # We use a deterministic UUID namespace to convert string chunk_ids
    # into UUIDs required by Qdrant.
    _NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    def __init__(
        self,
        connection_manager: QdrantConnectionManager,
        collection_name: str = "omniops_chunks",
    ) -> None:
        self._client = connection_manager.client
        self._collection_name = collection_name

    def ensure_collection(self, dimension: int) -> None:
        """Create the collection if it does not already exist."""
        if not self._client.collection_exists(self._collection_name):
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            # Create payload indexes for faster filtering
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    @classmethod
    def _deterministic_uuid(cls, chunk_id: str) -> str:
        """Generate a deterministic UUID from the chunk_id."""
        return str(uuid.uuid5(cls._NAMESPACE, chunk_id))

    def upsert_chunks(
        self, chunks: ChunkCollection, embeddings: list[list[float]]
    ) -> None:
        if len(chunks.chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks.chunks)} chunks vs {len(embeddings)} embeddings"
            )
        if not chunks.chunks or not embeddings:
            return

        # Ensure collection exists before upserting
        self.ensure_collection(dimension=len(embeddings[0]))

        points: list[models.PointStruct] = []
        for chunk, embedding in zip(chunks.chunks, embeddings):
            payload: dict[str, Any] = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "page_index": chunk.page_index,
                "section": chunk.section,
                "text": chunk.text,
            }
            # Add arbitrary metadata without overwriting top-level fields
            for key, value in chunk.metadata.items():
                if key not in payload:
                    payload[key] = value

            points.append(
                models.PointStruct(
                    id=self._deterministic_uuid(chunk.chunk_id),
                    vector=embedding,
                    payload=payload,
                )
            )

        # Batch upsert points. If a point with the same ID already exists,
        # it is safely overwritten (idempotent).
        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
        )

    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        
        query_filter = None
        if document_id is not None:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )

        scored_points = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        results: list[SearchResult] = []
        for point in scored_points:
            payload = point.payload or {}
            
            # Extract standard fields
            c_id = payload.pop("chunk_id", "")
            d_id = payload.pop("document_id", "")
            text = payload.pop("text", "")
            page_index = payload.pop("page_index", 0)
            section = payload.pop("section", None)
            
            # Remove chunk_index from payload to just leave pure metadata, though
            # it's harmless to keep. We'll pop it to keep metadata clean.
            payload.pop("chunk_index", None)

            results.append(
                SearchResult(
                    chunk_id=c_id,
                    document_id=d_id,
                    text=text,
                    score=point.score,
                    page_index=page_index,
                    section=section,
                    metadata=payload,
                )
            )
        return results

    def delete_document(self, document_id: str) -> None:
        if not self._client.collection_exists(self._collection_name):
            return
            
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            )
        )
