"""Chain of Verification (CoV) engine for industrial deliverables and permits."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from agents.intent_interpreter import _EQUIPMENT_TAG_PATTERN
from verification.evidence_ledger import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

_NUMERICAL_PARAMETER_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:psig|bar|kpa|mpa|°c|°f|k|gpm|m3/h|rpm|kw|hp|%|ppm|vol%|lel)\b",
    re.IGNORECASE,
)
_ISOLATION_ACTION_PATTERN = re.compile(
    r"\b(isolate|lockout|tagout|loto|close|blind|de-energize|disconnect|drain|vent|purge)\b",
    re.IGNORECASE,
)


@dataclass
class CoVClaim:
    """An individual atomic factual claim to be verified."""

    claim_id: str
    claim_text: str
    field_name: str
    verification_question: str
    status: VerificationStatus = VerificationStatus.UNVERIFIED_REQUIRES_HUMAN_CHECK
    exact_source_quote: str = ""
    source_document_id: str = ""
    page_index: int = 0
    chunk_id: str = ""
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "field_name": self.field_name,
            "verification_question": self.verification_question,
            "status": self.status.value,
            "exact_source_quote": self.exact_source_quote,
            "source_document_id": self.source_document_id,
            "page_index": self.page_index,
            "chunk_id": self.chunk_id,
            "reasoning": self.reasoning,
        }


class ChainOfVerification:
    """Executes Chain of Verification (CoV) claim decomposition and evidence cross-examination."""

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._llm = llm_provider

    def decompose_text(self, text: str) -> list[CoVClaim]:
        """Decompose free text into atomic verifiable claims with targeted questions."""
        claims: list[CoVClaim] = []
        if not text:
            return claims

        # Split text into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        for idx, sentence in enumerate(sentences, start=1):
            claim_id = f"CLM-{idx:03d}"
            tags = _EQUIPMENT_TAG_PATTERN.findall(sentence)
            params = _NUMERICAL_PARAMETER_PATTERN.findall(sentence)
            is_isolation = bool(_ISOLATION_ACTION_PATTERN.search(sentence))

            # Determine field and question
            if tags:
                field_name = "equipment_isolation" if is_isolation else "equipment_specification"
                question = f"Does the documentation confirm the actions or specification for equipment {', '.join(set(tags))}?"
            elif params:
                field_name = "operating_parameters"
                question = f"Are the specified operating parameters ({', '.join(set(params))}) verified in the source documentation?"
            elif is_isolation:
                field_name = "safety_isolation"
                question = "Does approved procedure require this specific isolation sequence?"
            else:
                field_name = "general_statement"
                question = "Is this statement corroborated by retrieved engineering documentation?"

            claims.append(
                CoVClaim(
                    claim_id=claim_id,
                    claim_text=sentence,
                    field_name=field_name,
                    verification_question=question,
                )
            )

        return claims

    def decompose_permit_fields(self, permit_data: dict[str, Any]) -> list[CoVClaim]:
        """Decompose structured industrial permit fields into atomic verifiable claims."""
        claims: list[CoVClaim] = []
        idx = 1

        for field_name, value in permit_data.items():
            if not value or field_name in ("permit_id", "status", "created_at", "updated_at"):
                continue

            if isinstance(value, list):
                for item in value:
                    item_str = str(item).strip()
                    if item_str:
                        claim_id = f"CLM-{idx:03d}"
                        idx += 1
                        question = f"Is the requirement '{item_str}' for field '{field_name}' verified by approved site procedures?"
                        claims.append(
                            CoVClaim(
                                claim_id=claim_id,
                                claim_text=item_str,
                                field_name=field_name,
                                verification_question=question,
                            )
                        )
            elif isinstance(value, dict):
                for sub_k, sub_v in value.items():
                    sub_str = str(sub_v).strip()
                    if sub_str:
                        claim_id = f"CLM-{idx:03d}"
                        idx += 1
                        question = f"Is {sub_k}='{sub_str}' in {field_name} verified by site documentation?"
                        claims.append(
                            CoVClaim(
                                claim_id=claim_id,
                                claim_text=f"{sub_k}: {sub_str}",
                                field_name=f"{field_name}.{sub_k}",
                                verification_question=question,
                            )
                        )
            else:
                val_str = str(value).strip()
                claim_id = f"CLM-{idx:03d}"
                idx += 1
                question = f"Is '{val_str}' verified for permit field '{field_name}'?"
                claims.append(
                    CoVClaim(
                        claim_id=claim_id,
                        claim_text=val_str,
                        field_name=field_name,
                        verification_question=question,
                    )
                )

        return claims

    def _extract_chunk_info(self, chunk: Any) -> tuple[str, str, int, str]:
        """Normalize chunk representation into (text, doc_id, page_index, chunk_id)."""
        if isinstance(chunk, str):
            return chunk, "doc-unknown", 1, f"chk-{uuid.uuid4().hex[:6]}"
        if isinstance(chunk, dict):
            text = chunk.get("text") or chunk.get("content") or ""
            doc_id = chunk.get("document_id") or chunk.get("doc_id") or "doc-unknown"
            page_index = chunk.get("page_index") or chunk.get("page_number") or 1
            chunk_id = chunk.get("chunk_id") or chunk.get("id") or f"chk-{uuid.uuid4().hex[:6]}"
            return text, str(doc_id), int(page_index), str(chunk_id)

        # Object representation (e.g. RetrievedChunk)
        text = getattr(chunk, "text", "") or getattr(chunk, "content", "")
        doc_id = getattr(chunk, "document_id", "doc-unknown")
        page_index = getattr(chunk, "page_index", 1)
        chunk_id = getattr(chunk, "chunk_id", f"chk-{uuid.uuid4().hex[:6]}")
        return str(text), str(doc_id), int(page_index), str(chunk_id)

    def verify_claim(self, claim: CoVClaim, chunks: list[Any]) -> CoVClaim:
        """Verify a single claim against available context chunks."""
        if not chunks:
            claim.status = VerificationStatus.UNVERIFIED_REQUIRES_HUMAN_CHECK
            claim.reasoning = "No source chunks provided for verification."
            return claim

        claim_lower = claim.claim_text.lower()
        tags = set(_EQUIPMENT_TAG_PATTERN.findall(claim.claim_text))
        params = set(_NUMERICAL_PARAMETER_PATTERN.findall(claim.claim_text))

        best_match_quote = ""
        best_doc_id = ""
        best_page = 1
        best_chunk_id = ""
        found_contradiction = False
        contradiction_reason = ""

        for chunk in chunks:
            chunk_text, doc_id, page, chk_id = self._extract_chunk_info(chunk)
            chunk_lower = chunk_text.lower()

            # 1. Contradiction check: Check for numerical contradictions
            # e.g. claim says 25% LEL but source says 10% LEL
            if "lel" in claim_lower and "lel" in chunk_lower:
                m_claim = re.search(r"(\d+(?:\.\d+)?)\s*%", claim_lower)
                m_chunk = re.search(r"(\d+(?:\.\d+)?)\s*%", chunk_lower)
                if m_claim and m_chunk and m_claim.group(1) != m_chunk.group(1):
                    found_contradiction = True
                    contradiction_reason = f"Source specifies {m_chunk.group(1)}% LEL, contradicting claim's {m_claim.group(1)}%."
                    break

            # 2. Corroboration check
            # Equipment tag match
            tag_match = bool(tags and any(tag.lower() in chunk_lower for tag in tags))
            # Parameter match
            param_match = bool(params and any(param.lower() in chunk_lower for param in params))

            # Word overlap match
            claim_words = [w for w in re.findall(r"\b\w{4,}\b", claim_lower) if w not in ("with", "from", "that", "this", "must", "have")]
            matched_words = [w for w in claim_words if w in chunk_lower]
            word_overlap_ratio = len(matched_words) / max(len(claim_words), 1)

            if tag_match or (param_match and word_overlap_ratio >= 0.4) or word_overlap_ratio >= 0.65:
                # Find matching sentence for exact quote
                chunk_sentences = re.split(r"(?<=[.!?])\s+", chunk_text)
                matching_sentence = ""
                for s in chunk_sentences:
                    if any(t.lower() in s.lower() for t in tags) or any(w in s.lower() for w in matched_words):
                        matching_sentence = s.strip()
                        break
                best_match_quote = matching_sentence or chunk_text[:200]
                best_doc_id = doc_id
                best_page = page
                best_chunk_id = chk_id
                break

        if found_contradiction:
            claim.status = VerificationStatus.CONTRADICTED
            claim.reasoning = contradiction_reason
        elif best_match_quote:
            claim.status = VerificationStatus.VERIFIED
            claim.exact_source_quote = best_match_quote
            claim.source_document_id = best_doc_id
            claim.page_index = best_page
            claim.chunk_id = best_chunk_id
            claim.reasoning = "Corroborated by source documentation."
        else:
            claim.status = VerificationStatus.UNVERIFIED_REQUIRES_HUMAN_CHECK
            claim.reasoning = "No corroborating evidence found in retrieved chunks."

        return claim

    def verify(
        self,
        claims_or_content: str | list[CoVClaim] | dict[str, Any],
        chunks: list[Any],
        artifact_id: str = "art-cov-default",
    ) -> EvidenceLedger:
        """Decompose, verify claims against chunks, and assemble an immutable EvidenceLedger."""
        if isinstance(claims_or_content, str):
            claims = self.decompose_text(claims_or_content)
        elif isinstance(claims_or_content, dict):
            claims = self.decompose_permit_fields(claims_or_content)
        elif isinstance(claims_or_content, list):
            claims = claims_or_content
        else:
            claims = []

        ledger = EvidenceLedger(artifact_id=artifact_id)

        for claim in claims:
            verified_claim = self.verify_claim(claim, chunks)
            entry = EvidenceLedgerEntry(
                claim_id=verified_claim.claim_id,
                claim_text=verified_claim.claim_text,
                field_name=verified_claim.field_name,
                source_document_id=verified_claim.source_document_id,
                page_index=verified_claim.page_index,
                chunk_id=verified_claim.chunk_id,
                exact_source_quote=verified_claim.exact_source_quote or verified_claim.reasoning,
                verification_status=verified_claim.status,
                verifier="CoV-Engine",
            )
            ledger.add_entry(entry)

        return ledger
