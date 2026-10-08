"""Deterministic query intent detection for the Retrieval Engine.

Implements Stage 1 of the Retrieval Pipeline (05_RETRIEVAL_ENGINE.md).
Classification is keyword-based and fully testable without infrastructure.
The LLM never participates in intent detection — this is a pure NLP stage.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Supported industrial query intents.

    Values match the canonical list in 05_RETRIEVAL_ENGINE.md Stage 1.
    """

    MAINTENANCE = "maintenance"
    COMPLIANCE = "compliance"
    ASSET_LOOKUP = "asset_lookup"
    TROUBLESHOOTING = "troubleshooting"
    EXPLANATION = "explanation"
    SUMMARY = "summary"
    TIMELINE = "timeline"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"


@dataclass(frozen=True)
class DetectedIntent:
    """Result of intent classification.

    Attributes:
        intent: The classified intent type.
        confidence: Score between 0.0 and 1.0 indicating match strength.
        matched_keywords: The keywords that contributed to classification.
    """

    intent: IntentType
    confidence: float
    matched_keywords: tuple[str, ...]


# ---------------------------------------------------------------------------
# Keyword lexicon per intent
# ---------------------------------------------------------------------------
# Each entry maps an IntentType to a dict of { keyword_or_phrase: weight }.
# Longer, more specific phrases get higher weights to reward precision.
# All keywords are stored lowercase; queries are lowered before matching.
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: dict[IntentType, dict[str, float]] = {
    IntentType.MAINTENANCE: {
        "maintenance": 1.0,
        "maintenance schedule": 1.5,
        "preventive maintenance": 1.8,
        "predictive maintenance": 1.8,
        "corrective maintenance": 1.8,
        "service interval": 1.5,
        "service history": 1.5,
        "overhaul": 1.2,
        "lubrication": 1.2,
        "calibration": 1.2,
        "inspection": 1.0,
        "work order": 1.3,
        "repair": 1.0,
        "spare part": 1.2,
        "replacement": 0.8,
        "downtime": 1.0,
        "planned outage": 1.4,
        "shutdown": 0.8,
        "next service": 1.4,
        "last serviced": 1.4,
        "when was it maintained": 1.6,
        "maintenance procedure": 1.6,
        "maintenance record": 1.5,
    },
    IntentType.COMPLIANCE: {
        "compliance": 1.5,
        "regulation": 1.3,
        "regulatory": 1.3,
        "standard": 0.8,
        "iso": 1.2,
        "osha": 1.5,
        "nfpa": 1.5,
        "api standard": 1.5,
        "code requirement": 1.4,
        "safety standard": 1.4,
        "audit": 1.2,
        "certification": 1.2,
        "permit": 1.0,
        "violation": 1.3,
        "non-compliance": 1.8,
        "compliant": 1.2,
        "meets requirements": 1.3,
        "regulatory requirement": 1.6,
        "safety regulation": 1.6,
        "environmental regulation": 1.6,
        "inspection requirement": 1.3,
    },
    IntentType.ASSET_LOOKUP: {
        "what is": 0.6,
        "tell me about": 0.8,
        "information about": 0.8,
        "details of": 0.8,
        "specifications": 1.2,
        "spec": 0.8,
        "specs": 0.8,
        "model number": 1.2,
        "serial number": 1.2,
        "manufacturer": 1.0,
        "location of": 1.0,
        "where is": 0.9,
        "asset": 1.0,
        "equipment": 0.8,
        "installed": 0.8,
        "rating": 0.8,
        "capacity": 0.8,
        "nameplate": 1.2,
        "data sheet": 1.2,
        "datasheet": 1.2,
    },
    IntentType.TROUBLESHOOTING: {
        "troubleshoot": 1.8,
        "troubleshooting": 1.8,
        "not working": 1.5,
        "malfunction": 1.5,
        "error": 0.8,
        "fault": 1.2,
        "alarm": 1.2,
        "trip": 1.0,
        "tripped": 1.0,
        "failure": 1.0,
        "failed": 1.0,
        "problem": 0.8,
        "issue": 0.6,
        "fix": 0.8,
        "how to fix": 1.5,
        "how to resolve": 1.5,
        "vibrating": 1.2,
        "vibration": 1.2,
        "overheating": 1.3,
        "leaking": 1.3,
        "leak": 1.0,
        "noise": 1.0,
        "unusual noise": 1.4,
        "won't start": 1.5,
        "does not start": 1.5,
        "stuck": 1.0,
        "diagnose": 1.5,
        "symptom": 1.2,
    },
    IntentType.EXPLANATION: {
        "explain": 1.2,
        "how does": 1.2,
        "how do": 1.0,
        "what does": 1.0,
        "what happens": 1.0,
        "describe": 1.0,
        "definition": 1.0,
        "meaning": 0.8,
        "purpose": 0.8,
        "function of": 1.0,
        "principle": 1.0,
        "how it works": 1.4,
        "working principle": 1.4,
        "mechanism": 1.0,
        "process": 0.6,
        "why does": 0.8,
        "concept": 0.8,
    },
    IntentType.SUMMARY: {
        "summary": 1.5,
        "summarize": 1.5,
        "overview": 1.3,
        "brief": 0.8,
        "key points": 1.3,
        "highlights": 1.0,
        "executive summary": 1.8,
        "report summary": 1.5,
        "give me a summary": 1.8,
        "sum up": 1.2,
        "in short": 1.0,
        "recap": 1.2,
        "abstract": 0.8,
        "overall": 0.6,
    },
    IntentType.TIMELINE: {
        "timeline": 1.8,
        "chronology": 1.5,
        "history": 1.0,
        "when did": 1.2,
        "when was": 1.2,
        "date of": 1.0,
        "sequence of events": 1.6,
        "event history": 1.5,
        "over time": 1.0,
        "time range": 1.0,
        "between dates": 1.3,
        "from date": 1.0,
        "last year": 0.8,
        "past month": 0.8,
        "recent events": 1.2,
        "chronological": 1.5,
        "order of events": 1.5,
    },
    IntentType.ROOT_CAUSE_ANALYSIS: {
        "root cause": 2.0,
        "root cause analysis": 2.5,
        "rca": 2.0,
        "why did": 1.2,
        "cause of": 1.2,
        "caused by": 1.2,
        "contributing factor": 1.5,
        "failure analysis": 1.8,
        "failure mode": 1.5,
        "what caused": 1.5,
        "reason for": 1.0,
        "origin of": 0.8,
        "underlying cause": 1.8,
        "5 whys": 2.0,
        "five whys": 2.0,
        "fishbone": 1.5,
        "ishikawa": 1.5,
        "fault tree": 1.5,
    },
}


class IntentDetector:
    """Deterministic keyword-based query intent classifier.

    Scores a query against weighted keyword lexicons for each intent type
    and returns the best match. No LLM calls or database queries are made.
    """

    # Minimum total score required to classify with confidence.
    # Below this threshold, the classifier falls back to EXPLANATION.
    _MIN_SCORE_THRESHOLD: float = 0.5

    def __init__(
        self,
        intent_keywords: dict[IntentType, dict[str, float]] | None = None,
    ) -> None:
        """Initialize with optional custom keyword lexicon for testing."""
        self._keywords = intent_keywords or _INTENT_KEYWORDS

    def detect(self, query: str) -> DetectedIntent:
        """Classify the query into a supported industrial intent.

        Args:
            query: The raw user question text.

        Returns:
            A DetectedIntent with the best matching intent, confidence,
            and the keywords that contributed to the score.
        """
        if not query or not query.strip():
            logger.warning("Empty query received for intent detection.")
            return DetectedIntent(
                intent=IntentType.EXPLANATION,
                confidence=0.0,
                matched_keywords=(),
            )

        normalized = query.lower().strip()

        best_intent = IntentType.EXPLANATION
        best_score: float = 0.0
        best_keywords: list[str] = []

        for intent_type, keyword_weights in self._keywords.items():
            score, matched = self._score_intent(normalized, keyword_weights)
            if score > best_score:
                best_score = score
                best_intent = intent_type
                best_keywords = matched

        # Apply confidence normalization
        confidence = self._normalize_confidence(best_score)

        # Fall back to EXPLANATION if score is too weak
        if best_score < self._MIN_SCORE_THRESHOLD:
            logger.info(
                "Intent score %.2f below threshold; defaulting to EXPLANATION.",
                best_score,
            )
            return DetectedIntent(
                intent=IntentType.EXPLANATION,
                confidence=confidence,
                matched_keywords=tuple(best_keywords),
            )

        logger.info(
            "Detected intent=%s confidence=%.2f keywords=%s",
            best_intent.value,
            confidence,
            best_keywords,
        )

        return DetectedIntent(
            intent=best_intent,
            confidence=confidence,
            matched_keywords=tuple(best_keywords),
        )

    @staticmethod
    def _score_intent(
        normalized_query: str,
        keyword_weights: dict[str, float],
    ) -> tuple[float, list[str]]:
        """Score a query against a single intent's keyword lexicon.

        Longer phrases are checked first (greedy matching) to avoid
        double-counting substrings.
        """
        total_score: float = 0.0
        matched: list[str] = []

        # Sort keywords by length descending so longer phrases match first
        sorted_keywords = sorted(
            keyword_weights.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        # Track which character positions have already been matched
        matched_positions: set[int] = set()

        for keyword, weight in sorted_keywords:
            for match in re.finditer(re.escape(keyword), normalized_query):
                start, end = match.start(), match.end()
                # Only count if positions haven't been claimed by a longer phrase
                positions = set(range(start, end))
                if not positions & matched_positions:
                    matched_positions |= positions
                    total_score += weight
                    matched.append(keyword)

        return total_score, matched

    @staticmethod
    def _normalize_confidence(raw_score: float) -> float:
        """Map raw keyword score to a 0.0–1.0 confidence using a sigmoid-like curve.

        Scores around 2.0 map to ~0.5 confidence; scores above 5.0 approach 1.0.
        """
        if raw_score <= 0.0:
            return 0.0
        # Simple logistic-style mapping: 1 - 1/(1 + score/2)
        return min(1.0, round(1.0 - 1.0 / (1.0 + raw_score / 2.0), 3))

    def to_dict(self, detected: DetectedIntent) -> dict[str, Any]:
        """Serialize a DetectedIntent to a JSON-safe dict.

        Matches the output format specified in 05_RETRIEVAL_ENGINE.md:
        ``{"intent": "maintenance", "confidence": 0.85, ...}``
        """
        return {
            "intent": detected.intent.value,
            "confidence": detected.confidence,
            "matched_keywords": list(detected.matched_keywords),
        }
