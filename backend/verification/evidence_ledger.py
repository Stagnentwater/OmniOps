"""Structured Evidence Ledger for verifiable auditability of industrial deliverables."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class VerificationStatus(str, Enum):
    """Integrity and grounding status of an individual claim."""

    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED_REQUIRES_HUMAN_CHECK = "UNVERIFIED_REQUIRES_HUMAN_CHECK"


@dataclass
class EvidenceLedgerEntry:
    """An individual verified claim linked directly to source evidence."""

    claim_id: str
    claim_text: str
    field_name: str
    source_document_id: str
    page_index: int
    chunk_id: str
    exact_source_quote: str
    verification_status: VerificationStatus
    verifier: str = "CoV-Engine"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "field_name": self.field_name,
            "source_document_id": self.source_document_id,
            "page_index": self.page_index,
            "chunk_id": self.chunk_id,
            "exact_source_quote": self.exact_source_quote,
            "verification_status": self.verification_status.value,
            "verifier": self.verifier,
            "timestamp": self.timestamp,
        }


@dataclass
class EvidenceLedger:
    """Immutable evidence ledger linking all critical claims to source documents."""

    artifact_id: str
    ledger_id: str = field(default_factory=lambda: f"led-{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entries: list[EvidenceLedgerEntry] = field(default_factory=list)

    def add_entry(self, entry: EvidenceLedgerEntry) -> None:
        self.entries.append(entry)

    def summary(self) -> dict[str, Any]:
        """Produce verification totals for UI display and sign-off gating."""
        total = len(self.entries)
        verified = sum(1 for e in self.entries if e.verification_status == VerificationStatus.VERIFIED)
        unverified = sum(1 for e in self.entries if e.verification_status == VerificationStatus.UNVERIFIED_REQUIRES_HUMAN_CHECK)
        contradicted = sum(1 for e in self.entries if e.verification_status == VerificationStatus.CONTRADICTED)

        return {
            "total_claims": total,
            "verified_claims": verified,
            "unverified_claims": unverified,
            "contradicted_claims": contradicted,
            "all_verified": (total > 0 and verified == total),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "artifact_id": self.artifact_id,
            "created_at": self.created_at,
            "summary": self.summary(),
            "entries": [e.to_dict() for e in self.entries],
        }
