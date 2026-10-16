"""Domain data models for evidence-grounded Industrial Work Permits."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from verification.evidence_ledger import EvidenceLedger


class PermitType(str, Enum):
    """Supported industrial permit classifications."""

    GENERAL_WORK = "general_work"
    HOT_WORK = "hot_work"
    COLD_WORK = "cold_work"
    CONFINED_SPACE_ENTRY = "confined_space_entry"
    LOCKOUT_TAGOUT = "lockout_tagout"


class PermitStatus(str, Enum):
    """Deterministic status state machine for industrial permits."""

    DRAFT_GENERATED = "DRAFT_GENERATED"
    VERIFICATION_INCOMPLETE = "VERIFICATION_INCOMPLETE"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    AUTHORIZED_BY_HUMAN = "AUTHORIZED_BY_HUMAN"


@dataclass
class GasTestingRequirements:
    """Atmospheric and toxic gas limits for safe entry or hot work."""

    oxygen_min_percent: float = 19.5
    oxygen_max_percent: float = 23.5
    lel_max_percent: float = 10.0
    h2s_max_ppm: float = 10.0
    co_max_ppm: float = 25.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "oxygen_min_percent": self.oxygen_min_percent,
            "oxygen_max_percent": self.oxygen_max_percent,
            "lel_max_percent": self.lel_max_percent,
            "h2s_max_ppm": self.h2s_max_ppm,
            "co_max_ppm": self.co_max_ppm,
        }


@dataclass
class IsolationPoint:
    """Specific valve, electrical breaker, or blind for hazardous energy isolation."""

    tag: str
    isolation_type: str
    status: str
    location: str = ""
    verified_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "isolation_type": self.isolation_type,
            "status": self.status,
            "location": self.location,
            "verified_by": self.verified_by,
        }


@dataclass
class IndustrialPermit:
    """Complete industrial permit draft with evidence ledger and verification tracking."""

    permit_id: str = field(default_factory=lambda: f"PERMIT-{uuid.uuid4().hex[:8].upper()}")
    permit_type: PermitType = PermitType.GENERAL_WORK
    status: PermitStatus = PermitStatus.DRAFT_GENERATED
    title: str = "Industrial Work Permit"
    work_order_number: str = "WO-PENDING"
    facility_name: str = "Refinery / Plant Facility"
    unit_area: str = "General Process Unit"
    equipment_tag: str = ""
    equipment_description: str = ""
    work_description: str = ""
    hazards_identified: list[str] = field(default_factory=list)
    required_precautions: list[str] = field(default_factory=list)
    required_ppe: list[str] = field(default_factory=list)
    isolation_points: list[IsolationPoint] = field(default_factory=list)
    gas_testing: GasTestingRequirements | None = None
    fire_watch_required: bool = False
    standby_personnel_required: bool = False
    special_instructions: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    evidence_ledger: EvidenceLedger | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authorized_by: str | None = None
    authorized_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "permit_id": self.permit_id,
            "permit_type": self.permit_type.value,
            "status": self.status.value,
            "title": self.title,
            "work_order_number": self.work_order_number,
            "facility_name": self.facility_name,
            "unit_area": self.unit_area,
            "equipment_tag": self.equipment_tag,
            "equipment_description": self.equipment_description,
            "work_description": self.work_description,
            "hazards_identified": list(self.hazards_identified),
            "required_precautions": list(self.required_precautions),
            "required_ppe": list(self.required_ppe),
            "isolation_points": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.isolation_points],
            "gas_testing": self.gas_testing.to_dict() if hasattr(self.gas_testing, "to_dict") else self.gas_testing,
            "fire_watch_required": self.fire_watch_required,
            "standby_personnel_required": self.standby_personnel_required,
            "special_instructions": list(self.special_instructions),
            "missing_information": list(self.missing_information),
            "evidence_ledger": self.evidence_ledger.to_dict() if hasattr(self.evidence_ledger, "to_dict") else self.evidence_ledger,
            "created_at": self.created_at,
            "authorized_by": self.authorized_by,
            "authorized_at": self.authorized_at,
        }
