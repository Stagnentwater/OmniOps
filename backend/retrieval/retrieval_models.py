"""Data models for the Retrieval Layer output context."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from retrieval.intent_detector import DetectedIntent
    from retrieval.asset_detector import AssetDetectionResult
    from retrieval.evidence_ranker import RankingSignals


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
    
    After Stage 6 (Evidence Ranking), ranked_chunks contains the re-ordered
    evidence and ranking_explanations provides per-chunk signal breakdowns.
    """
    
    query: str
    chunks: tuple[RetrievedChunk, ...]
    entities: tuple[RetrievedEntity, ...]
    relationships: tuple[RetrievedRelationship, ...]
    intent: DetectedIntent | None = None
    detected_assets: AssetDetectionResult | None = None
    ranked_chunks: tuple[RetrievedChunk, ...] | None = None
    ranking_explanations: dict[str, RankingSignals] | None = None
