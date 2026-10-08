"""Evidence Ranking for the Retrieval Pipeline (Stage 6).

Implements the cross-source ranking stage defined in 05_RETRIEVAL_ENGINE.md.
Merges and re-ranks vector and graph evidence using multiple explainable
signals without altering citation provenance.

Ranking signals (per spec):
- semantic_similarity:     Vector similarity score from Qdrant
- graph_relevance:         Whether the chunk's document is connected to detected assets
- asset_match:             Whether the chunk mentions a detected asset
- recency:                 Prefer newer documents (if timestamp available)
- provenance_completeness: Chunks with richer metadata rank higher
- source_priority:         Boost chunks from authoritative document types
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from retrieval.retrieval_models import (
        RetrievedChunk,
        RetrievedEntity,
        RetrievalContext,
    )
    from retrieval.asset_detector import AssetDetectionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RankingSignals:
    """Explainable breakdown of why a chunk was ranked at its position.

    Each signal is a float between 0.0 and 1.0.
    The final_score is a weighted combination of all signals.
    """

    semantic_similarity: float
    graph_relevance: float
    asset_match: float
    recency: float
    provenance_completeness: float
    source_priority: float
    final_score: float


# Weights for each ranking signal (sum to 1.0 for interpretability)
_DEFAULT_WEIGHTS = {
    "semantic_similarity": 0.35,
    "graph_relevance": 0.20,
    "asset_match": 0.20,
    "recency": 0.05,
    "provenance_completeness": 0.10,
    "source_priority": 0.10,
}

# Document types considered high-authority for industrial knowledge
_AUTHORITY_TYPES = frozenset({
    "maintenance_manual", "technical_specification", "safety_report",
    "inspection_report", "engineering_standard", "regulatory_document",
    "pid", "procedure", "work_order",
})


class EvidenceRanker:
    """Re-ranks retrieved chunks using multiple explainable signals.

    The ranker does NOT modify chunk content or citation provenance.
    It only reorders the evidence and attaches explainable ranking signals.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._weights = weights or _DEFAULT_WEIGHTS

    def rank(
        self,
        context: RetrievalContext,
    ) -> tuple[tuple[RetrievedChunk, ...], dict[str, RankingSignals]]:
        """Rank chunks from a RetrievalContext using multiple signals.

        Args:
            context: The assembled retrieval context containing chunks,
                entities, relationships, detected assets, and intent.

        Returns:
            A tuple of (ranked_chunks, ranking_explanations).
            ranked_chunks: Chunks reordered by final_score descending.
            ranking_explanations: A dict mapping chunk_id to RankingSignals.
        """
        if not context.chunks:
            return (), {}

        # Pre-compute lookup structures
        graph_doc_ids = self._extract_graph_document_ids(context.entities)
        asset_names = self._extract_asset_names(context.detected_assets)

        # Score each chunk
        scored: list[tuple[RetrievedChunk, RankingSignals]] = []
        for chunk in context.chunks:
            signals = self._compute_signals(
                chunk=chunk,
                graph_doc_ids=graph_doc_ids,
                asset_names=asset_names,
            )
            scored.append((chunk, signals))

        # Sort by final_score descending (stable sort preserves original order for ties)
        scored.sort(key=lambda pair: pair[1].final_score, reverse=True)

        ranked_chunks = tuple(chunk for chunk, _ in scored)
        explanations = {chunk.chunk_id: signals for chunk, signals in scored}

        logger.info(
            "Evidence ranked: %d chunks, top_score=%.3f, bottom_score=%.3f",
            len(ranked_chunks),
            scored[0][1].final_score if scored else 0.0,
            scored[-1][1].final_score if scored else 0.0,
        )

        return ranked_chunks, explanations

    def _compute_signals(
        self,
        *,
        chunk: RetrievedChunk,
        graph_doc_ids: set[str],
        asset_names: list[str],
    ) -> RankingSignals:
        """Compute all ranking signals for a single chunk."""
        sem_sim = self._signal_semantic_similarity(chunk)
        graph_rel = self._signal_graph_relevance(chunk, graph_doc_ids)
        asset_m = self._signal_asset_match(chunk, asset_names)
        recency = self._signal_recency(chunk)
        prov = self._signal_provenance_completeness(chunk)
        src_pri = self._signal_source_priority(chunk)

        w = self._weights
        final = (
            w["semantic_similarity"] * sem_sim
            + w["graph_relevance"] * graph_rel
            + w["asset_match"] * asset_m
            + w["recency"] * recency
            + w["provenance_completeness"] * prov
            + w["source_priority"] * src_pri
        )

        return RankingSignals(
            semantic_similarity=round(sem_sim, 4),
            graph_relevance=round(graph_rel, 4),
            asset_match=round(asset_m, 4),
            recency=round(recency, 4),
            provenance_completeness=round(prov, 4),
            source_priority=round(src_pri, 4),
            final_score=round(final, 4),
        )

    @staticmethod
    def _signal_semantic_similarity(chunk: RetrievedChunk) -> float:
        """Normalize Qdrant score to [0, 1].

        Qdrant cosine similarity is already in [-1, 1]. Most relevant
        results are in [0.3, 0.9]. We clamp and normalize.
        """
        raw = chunk.score
        # Clamp to [0, 1] — negative similarity means irrelevant
        return max(0.0, min(1.0, raw))

    @staticmethod
    def _signal_graph_relevance(
        chunk: RetrievedChunk,
        graph_doc_ids: set[str],
    ) -> float:
        """1.0 if the chunk's document appears in graph results, else 0.0."""
        if chunk.document_id in graph_doc_ids:
            return 1.0
        return 0.0

    @staticmethod
    def _signal_asset_match(
        chunk: RetrievedChunk,
        asset_names: list[str],
    ) -> float:
        """Score based on how many detected assets appear in chunk text."""
        if not asset_names:
            return 0.5  # Neutral when no assets detected

        text_lower = chunk.text.lower()
        matches = sum(1 for name in asset_names if name.lower() in text_lower)

        if matches == 0:
            return 0.0
        # Diminishing returns: 1 match = 0.7, 2+ = 1.0
        return min(1.0, 0.7 + (matches - 1) * 0.3)

    @staticmethod
    def _signal_recency(chunk: RetrievedChunk) -> float:
        """Score based on document recency from metadata.

        If no date metadata is available, return neutral 0.5.
        """
        meta = chunk.metadata
        # Check for common date fields
        for key in ("upload_time", "document_date", "created_at", "date"):
            if key in meta and meta[key]:
                # If a date exists, give a moderate boost — we don't parse
                # the actual date to avoid complexity; presence = recency signal
                return 0.7
        return 0.5

    @staticmethod
    def _signal_provenance_completeness(chunk: RetrievedChunk) -> float:
        """Score based on metadata richness.

        Chunks with more metadata fields are considered more traceable.
        """
        meta = chunk.metadata
        if not meta:
            return 0.0

        # Count meaningful metadata fields
        meaningful_keys = {
            "document_id", "filename", "section", "page_index",
            "document_type", "source_type", "upload_time",
            "has_tables", "has_images",
        }
        present = sum(1 for k in meaningful_keys if k in meta and meta[k])
        # Normalize: 5+ meaningful fields = 1.0
        return min(1.0, present / 5.0)

    @staticmethod
    def _signal_source_priority(chunk: RetrievedChunk) -> float:
        """Score based on document type authority.

        Maintenance manuals, safety reports, and technical specs
        rank higher than generic documents.
        """
        meta = chunk.metadata
        doc_type = str(meta.get("document_type", "")).lower().replace(" ", "_")
        source_type = str(meta.get("source_type", "")).lower().replace(" ", "_")

        if doc_type in _AUTHORITY_TYPES or source_type in _AUTHORITY_TYPES:
            return 1.0
        if doc_type or source_type:
            return 0.5  # Known type but not high-authority
        return 0.3  # Unknown type

    @staticmethod
    def _extract_graph_document_ids(
        entities: tuple[RetrievedEntity, ...] | None,
    ) -> set[str]:
        """Extract document IDs from graph entities for cross-referencing."""
        if not entities:
            return set()

        doc_ids: set[str] = set()
        for entity in entities:
            props = entity.properties
            for key in ("document_id", "source_document_id", "doc_id"):
                if key in props and props[key]:
                    doc_ids.add(str(props[key]))
        return doc_ids

    @staticmethod
    def _extract_asset_names(
        detected_assets: AssetDetectionResult | None,
    ) -> list[str]:
        """Extract asset names for text matching."""
        if detected_assets is None:
            return []

        names: list[str] = []
        for candidate in detected_assets.candidates:
            names.append(candidate.canonical_name)
            # Also include the raw mention for fuzzy matching
            if hasattr(candidate, "raw_mention") and candidate.raw_mention:
                names.append(candidate.raw_mention)
        return names
