"""Deterministic asset detection for the Retrieval Engine.

Implements Stage 2 of the Retrieval Pipeline (05_RETRIEVAL_ENGINE.md).
Extracts asset references from the query using the same regex patterns
as the ingestion entity extractor, then resolves them against the
Knowledge Graph to find known entities.

The LLM never participates in asset detection — this is a pure NLP + graph
lookup stage.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any

from graph.query_service import GraphQueryService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetCandidate:
    """A single candidate match between a query-referenced asset and a graph entity.

    Attributes:
        raw_mention: The exact text extracted from the query.
        entity_id: The graph entity_id, or None if unresolved.
        canonical_name: Human-readable name from the graph, or the raw mention.
        entity_type: Graph entity type (e.g. "Asset", "Component"), or "unknown".
        confidence: Score between 0.0 and 1.0.
        resolved: True if the candidate was matched to a known graph entity.
    """

    raw_mention: str
    entity_id: str | None
    canonical_name: str
    entity_type: str
    confidence: float
    resolved: bool


@dataclass(frozen=True)
class AssetDetectionResult:
    """Output of asset detection for a single query.

    Attributes:
        candidates: Tuple of all detected asset candidates (resolved + unresolved).
        resolved_count: Number of candidates that matched known graph entities.
        ambiguous: True if multiple graph entities matched a single mention.
    """

    candidates: tuple[AssetCandidate, ...]
    resolved_count: int
    ambiguous: bool


from utils.tag_patterns import TAG_REGEX, validate_and_parse_tag

# ---------------------------------------------------------------------------
# Regex patterns for extracting asset mentions from queries.
# These mirror the patterns in ingestion/extractor.py (ENT-001) to maintain
# consistency between what gets ingested and what gets detected at query time.
# ---------------------------------------------------------------------------

# Full asset mentions like "Pump P301", "Valve V-200", "Compressor C-100"
_ASSET_FULL_PATTERN = re.compile(
    r"\b(?i:Pump|Boiler|Valve|Compressor|Generator|Turbine|Motor|Fan|Chiller|Heater)\s+([A-Za-z0-9\-]+)\b"
)

# Component mentions like "bearing", "impeller", "seal"
_COMPONENT_PATTERN = re.compile(
    r"\b(bearing|seal|impeller|gasket|coupling|shaft|rotor|stator"
    r"|gearbox|piston|cylinder|motor)s?\b",
    re.IGNORECASE,
)


class AssetDetector:
    """Deterministic asset reference extractor and graph resolver.

    Extracts potential asset references from user queries using regex patterns,
    then attempts to resolve each reference against the Knowledge Graph.
    No LLM calls are made during detection or resolution.
    """

    def __init__(
        self,
        graph_service: GraphQueryService | None = None,
    ) -> None:
        """Initialize the detector.

        Args:
            graph_service: Optional graph service for resolution. If None,
                all candidates are returned as unresolved.
        """
        self._graph_service = graph_service

    def detect(self, query: str) -> AssetDetectionResult:
        """Extract and resolve asset references from a query.

        Args:
            query: The raw user question text.

        Returns:
            An AssetDetectionResult with all detected candidates.
        """
        if not query or not query.strip():
            logger.warning("Empty query received for asset detection.")
            return AssetDetectionResult(
                candidates=(),
                resolved_count=0,
                ambiguous=False,
            )

        mentions = self._extract_mentions(query)

        if not mentions:
            logger.info("No asset mentions detected in query.")
            return AssetDetectionResult(
                candidates=(),
                resolved_count=0,
                ambiguous=False,
            )

        # Resolve each mention against the graph
        candidates: list[AssetCandidate] = []
        ambiguous = False

        for mention in mentions:
            resolved_candidates = self._resolve_mention(mention)

            if len(resolved_candidates) > 1:
                ambiguous = True
                logger.info(
                    "Ambiguous asset mention '%s': %d graph matches.",
                    mention["raw"],
                    len(resolved_candidates),
                )

            if resolved_candidates:
                candidates.extend(resolved_candidates)
            else:
                # Unresolved: keep the mention as an unresolved candidate
                candidates.append(
                    AssetCandidate(
                        raw_mention=mention["raw"],
                        entity_id=None,
                        canonical_name=mention["raw"],
                        entity_type=mention["type"],
                        confidence=0.0,
                        resolved=False,
                    )
                )

        # Deduplicate by entity_id (keep highest confidence for each)
        deduped = self._deduplicate_candidates(candidates)

        resolved_count = sum(1 for c in deduped if c.resolved)
        logger.info(
            "Asset detection: %d mentions, %d candidates, %d resolved, ambiguous=%s",
            len(mentions),
            len(deduped),
            resolved_count,
            ambiguous,
        )

        return AssetDetectionResult(
            candidates=tuple(deduped),
            resolved_count=resolved_count,
            ambiguous=ambiguous,
        )

    def _extract_mentions(self, query: str) -> list[dict[str, str]]:
        """Extract raw asset mentions from query text using regex patterns.

        Returns a list of dicts with keys 'raw' (matched text) and
        'type' (category: 'asset', 'tag', or 'component').
        """
        mentions: list[dict[str, str]] = []
        seen_texts: set[str] = set()

        # 1. Full asset mentions: "Pump P301"
        for match in _ASSET_FULL_PATTERN.finditer(query):
            potential_tag = match.group(1)
            parsed = validate_and_parse_tag(potential_tag)
            if parsed:
                tag, _, _ = parsed
                # Use the extracted standard tag as raw
                raw = tag
                normalized = raw.lower()
                if normalized not in seen_texts:
                    seen_texts.add(normalized)
                    mentions.append({"raw": raw, "type": "asset"})

        # 2. Short tags: "P-301" (only if not already part of a full mention)
        for match in TAG_REGEX.finditer(query):
            orig = match.group(0).strip()
            parsed = validate_and_parse_tag(orig)
            if parsed:
                tag, _, _ = parsed
                raw = tag
                normalized = raw.lower()
                if normalized not in seen_texts:
                    # Check the tag isn't part of an already-captured full mention
                    already_captured = False
                    for seen in seen_texts:
                        if normalized in seen:
                            already_captured = True
                            break
                    if not already_captured:
                        seen_texts.add(normalized)
                        mentions.append({"raw": raw, "type": "tag"})

        # 3. Components: "bearing", "impeller"
        for match in _COMPONENT_PATTERN.finditer(query):
            raw = match.group(0).strip()
            normalized = raw.lower()
            if normalized not in seen_texts:
                seen_texts.add(normalized)
                mentions.append({"raw": raw, "type": "component"})

        return mentions

    def _resolve_mention(
        self,
        mention: dict[str, str],
    ) -> list[AssetCandidate]:
        """Attempt to resolve a mention against the Knowledge Graph.

        Returns a list of resolved AssetCandidates (may be empty or multiple).
        """
        if self._graph_service is None:
            return []

        raw_text = mention["raw"]

        try:
            graph_results = self._graph_service.search_nodes(raw_text, limit=5)
        except Exception as e:
            logger.error("Graph search failed for mention '%s': %s", raw_text, e)
            return []

        if not graph_results:
            return []

        candidates: list[AssetCandidate] = []
        for node in graph_results:
            entity_id = node.get("entity_id")
            if not entity_id:
                continue

            canonical_name = node.get("canonical_name", raw_text)
            entity_type = node.get("entity_type", "unknown")
            graph_confidence = node.get("confidence", 0.5)

            # Compute match confidence from name similarity
            name_similarity = self._compute_name_similarity(
                raw_text, canonical_name
            )

            # Combined confidence: graph confidence weighted with name match
            combined_confidence = min(
                1.0,
                round(0.4 * graph_confidence + 0.6 * name_similarity, 3),
            )

            candidates.append(
                AssetCandidate(
                    raw_mention=raw_text,
                    entity_id=entity_id,
                    canonical_name=canonical_name,
                    entity_type=entity_type,
                    confidence=combined_confidence,
                    resolved=True,
                )
            )

        return candidates

    @staticmethod
    def _compute_name_similarity(query_mention: str, canonical_name: str) -> float:
        """Compute a simple normalized similarity between mention and canonical name.

        Uses token overlap (Jaccard-like) for deterministic, explainable matching.
        """
        query_tokens = set(query_mention.lower().split())
        canonical_tokens = set(canonical_name.lower().split())

        if not query_tokens or not canonical_tokens:
            return 0.0

        intersection = query_tokens & canonical_tokens
        union = query_tokens | canonical_tokens

        return len(intersection) / len(union)

    @staticmethod
    def _deduplicate_candidates(
        candidates: list[AssetCandidate],
    ) -> list[AssetCandidate]:
        """Deduplicate by entity_id, keeping highest confidence for each.

        Unresolved candidates (entity_id=None) are always kept.
        """
        best_by_id: dict[str, AssetCandidate] = {}
        unresolved: list[AssetCandidate] = []

        for candidate in candidates:
            if candidate.entity_id is None:
                unresolved.append(candidate)
                continue

            existing = best_by_id.get(candidate.entity_id)
            if existing is None or candidate.confidence > existing.confidence:
                best_by_id[candidate.entity_id] = candidate

        # Resolved first (sorted by confidence desc), then unresolved
        resolved = sorted(
            best_by_id.values(),
            key=lambda c: c.confidence,
            reverse=True,
        )

        return list(resolved) + unresolved

    def to_dict(self, result: AssetDetectionResult) -> dict[str, Any]:
        """Serialize an AssetDetectionResult to a JSON-safe dict."""
        return {
            "candidates": [
                {
                    "raw_mention": c.raw_mention,
                    "entity_id": c.entity_id,
                    "canonical_name": c.canonical_name,
                    "entity_type": c.entity_type,
                    "confidence": c.confidence,
                    "resolved": c.resolved,
                }
                for c in result.candidates
            ],
            "resolved_count": result.resolved_count,
            "ambiguous": result.ambiguous,
        }
