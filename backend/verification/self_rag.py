"""Self-RAG Evidence Sufficiency Evaluator and Bounded Retrieval Loop."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.intent_interpreter import _EQUIPMENT_TAG_PATTERN

logger = logging.getLogger(__name__)


class SufficiencyStatus(str, Enum):
    """Classification of context sufficiency for technical answering."""

    SUFFICIENT = "sufficient"
    PARTIALLY_SUFFICIENT = "partially_sufficient"
    INSUFFICIENT = "insufficient"


@dataclass
class SufficiencyEvaluation:
    """Evaluation result detailing whether retrieved context supports the task."""

    status: SufficiencyStatus
    supported_parameters: list[str] = field(default_factory=list)
    missing_parameters: list[str] = field(default_factory=list)
    confidence: float = 1.0
    secondary_query: str | None = None
    reasoning: str = ""
    iteration: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "supported_parameters": self.supported_parameters,
            "missing_parameters": self.missing_parameters,
            "confidence": self.confidence,
            "secondary_query": self.secondary_query,
            "reasoning": self.reasoning,
            "iteration": self.iteration,
        }


class SelfRAGChecker:
    """Evaluates evidence sufficiency and executes bounded secondary retrieval."""

    def __init__(
        self,
        retrieval_service: Any | None = None,
        max_retries: int = 2,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._max_retries = max_retries

    def evaluate_sufficiency(
        self,
        query: str,
        context_chunks: list[Any],
        required_parameters: list[str] | None = None,
        iteration: int = 1,
    ) -> SufficiencyEvaluation:
        """Evaluate whether retrieved chunks cover all required parameters."""
        if not context_chunks:
            tags = _EQUIPMENT_TAG_PATTERN.findall(query)
            target = tags[0] if tags else "equipment"
            return SufficiencyEvaluation(
                status=SufficiencyStatus.INSUFFICIENT,
                supported_parameters=[],
                missing_parameters=required_parameters or ["technical_specifications"],
                confidence=0.0,
                secondary_query=f"{target} operating parameters safety isolation",
                reasoning="Zero context chunks available to verify technical claims.",
                iteration=iteration,
            )

        combined_text = " ".join(
            (getattr(c, "text", "") or "") for c in context_chunks
        ).lower()

        # If explicit required parameters provided, verify each
        params_to_check = required_parameters or [
            "pressure",
            "temperature",
            "isolation",
            "valve",
            "procedure",
            "safety",
        ]

        supported: list[str] = []
        missing: list[str] = []

        for param in params_to_check:
            if param.lower() in combined_text:
                supported.append(param)
            else:
                missing.append(param)

        ratio = len(supported) / max(len(params_to_check), 1)

        tags = _EQUIPMENT_TAG_PATTERN.findall(query)
        target = tags[0] if tags else ""

        if ratio >= 0.7:
            status = SufficiencyStatus.SUFFICIENT
            secondary_q = None
            reasoning = f"Context contains sufficient evidence ({len(supported)}/{len(params_to_check)} required parameters verified)."
        elif ratio > 0.0:
            status = SufficiencyStatus.PARTIALLY_SUFFICIENT
            missing_terms = " ".join(missing[:3])
            secondary_q = f"{target} {missing_terms}".strip()
            reasoning = f"Context is partially sufficient. Missing critical parameters: {', '.join(missing)}."
        else:
            status = SufficiencyStatus.INSUFFICIENT
            missing_terms = " ".join(missing[:3])
            secondary_q = f"{target} {missing_terms} specifications".strip()
            reasoning = f"Context lacks sufficient parameter grounding ({len(missing)} parameters missing)."

        return SufficiencyEvaluation(
            status=status,
            supported_parameters=supported,
            missing_parameters=missing,
            confidence=round(ratio, 2),
            secondary_query=secondary_q,
            reasoning=reasoning,
            iteration=iteration,
        )

    def retrieve_with_sufficiency_check(
        self,
        query: str,
        initial_chunks: list[Any] | None = None,
        required_parameters: list[str] | None = None,
    ) -> tuple[list[Any], SufficiencyEvaluation]:
        """Perform bounded Self-RAG loop, executing secondary retrieval if needed."""
        chunks = list(initial_chunks or [])
        iteration = 1

        # If no initial chunks, perform first retrieval pass
        if not chunks and self._retrieval_service is not None:
            ret_res = self._retrieval_service.retrieve(query, limit=5)
            chunks = getattr(ret_res, "chunks", []) or []

        evaluation = self.evaluate_sufficiency(query, chunks, required_parameters, iteration=iteration)

        # Bounded secondary retrieval loop (up to max_retries)
        while evaluation.status != SufficiencyStatus.SUFFICIENT and iteration < self._max_retries:
            if not evaluation.secondary_query or self._retrieval_service is None:
                break

            iteration += 1
            logger.info(
                "Self-RAG executing bounded secondary retrieval (iter %d/%d): '%s'",
                iteration,
                self._max_retries,
                evaluation.secondary_query,
            )

            try:
                sec_res = self._retrieval_service.retrieve(evaluation.secondary_query, limit=5)
                new_chunks = getattr(sec_res, "chunks", []) or []

                # Deduplicate by chunk_id
                seen_ids = {getattr(c, "chunk_id", id(c)) for c in chunks}
                for nc in new_chunks:
                    cid = getattr(nc, "chunk_id", id(nc))
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        chunks.append(nc)

                evaluation = self.evaluate_sufficiency(query, chunks, required_parameters, iteration=iteration)
            except Exception as e:
                logger.warning("Self-RAG secondary retrieval failed: %s", e)
                break

        return chunks, evaluation
