"""Calculation detector — determines if a query needs numeric computation.

Uses keyword/pattern matching (no LLM call) for the prototype.
This keeps the detector deterministic and fast.

Examples:
  "What pressure is reported?" → No calculation
  "Convert 350°F to Celsius"  → Calculation needed
  "Calculate the percentage change" → Calculation needed
  "What is 20% higher than X?" → Calculation needed
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Patterns that indicate a calculation is needed
_CALCULATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcalculate\b", re.IGNORECASE),
    re.compile(r"\bcompute\b", re.IGNORECASE),
    re.compile(r"\bconvert\b.*\b(to|into)\b", re.IGNORECASE),
    re.compile(r"\bwhat is\b.*\b(percent|percentage|%)\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*(%|percent)\s*(higher|lower|more|less|increase|decrease)", re.IGNORECASE),
    re.compile(r"\bhow much\b.*\b(if|when|after)\b", re.IGNORECASE),
    re.compile(r"\bremaining\s+(life|capacity|time)\b", re.IGNORECASE),
    re.compile(r"\bpressure\s+drop\b", re.IGNORECASE),
    re.compile(r"\bflow\s+rate\b.*\b(increase|decrease|change)\b", re.IGNORECASE),
    re.compile(r"\b(sum|total|average|mean|median)\s+of\b", re.IGNORECASE),
    re.compile(r"\b(multiply|divide|subtract|add)\b", re.IGNORECASE),
    re.compile(r"\bformula\b", re.IGNORECASE),
    re.compile(r"\b°[FC]\b.*\b(to|into)\b", re.IGNORECASE),
    re.compile(r"\bfahrenheit\b.*\b(to|celsius)\b", re.IGNORECASE),
    re.compile(r"\bcelsius\b.*\b(to|fahrenheit)\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class DetectionResult:
    """Result of calculation detection."""

    needs_calculation: bool
    confidence: float
    matched_pattern: str


class CalculationDetector:
    """Determines whether a query requires deterministic calculation.

    Uses pattern matching for the prototype. Does not invoke the LLM.
    """

    def __init__(
        self,
        patterns: list[re.Pattern[str]] | None = None,
    ) -> None:
        self._patterns = patterns or _CALCULATION_PATTERNS

    def detect(self, query: str) -> DetectionResult:
        """Check if the query needs calculation.

        Returns DetectionResult with needs_calculation=True if any
        calculation pattern matches.
        """
        if not query or not query.strip():
            return DetectionResult(
                needs_calculation=False,
                confidence=1.0,
                matched_pattern="",
            )

        for pattern in self._patterns:
            match = pattern.search(query)
            if match:
                logger.info(
                    "Calculation detected: pattern='%s' matched in query",
                    pattern.pattern,
                )
                return DetectionResult(
                    needs_calculation=True,
                    confidence=0.8,
                    matched_pattern=pattern.pattern,
                )

        return DetectionResult(
            needs_calculation=False,
            confidence=0.9,
            matched_pattern="",
        )
