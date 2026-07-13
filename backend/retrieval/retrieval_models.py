"""Data models for the Retrieval Layer output context."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievedChunk:
    """Represents a chunk retrieved from the vector database."""
    
    chunk_id: str
    document_id: str
    text: str
    score: float
    page_index: int
    section: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievedEntity:
    """Represents an entity node retrieved from the graph database."""
    
    entity_id: str
    entity_type: str
    canonical_name: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class RetrievedRelationship:
    """Represents an edge retrieved from the graph database."""
    
    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class RetrievalContext:
    """Unified deterministic context assembled from vector and graph retrievals.
    
    Acts as the strict data contract prior to any LLM reasoning. No data synthesis
    or score fusion is performed here.
    """
    
    query: str
    chunks: tuple[RetrievedChunk, ...]
    entities: tuple[RetrievedEntity, ...]
    relationships: tuple[RetrievedRelationship, ...]
