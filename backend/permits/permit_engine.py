"""Industrial Work Permit Drafting and Evidence Verification Engine."""

from __future__ import annotations

import logging
import re
from typing import Any

from agents.intent_interpreter import _EQUIPMENT_TAG_PATTERN
from permits.permit_models import (
    GasTestingRequirements,
    IndustrialPermit,
    IsolationPoint,
    PermitStatus,
    PermitType,
)
from verification.chain_of_verification import ChainOfVerification
from verification.evidence_ledger import VerificationStatus

logger = logging.getLogger(__name__)

_VALVE_PATTERN = re.compile(r"\b(MOV-\d+[A-Z]?|FCV-\d+[A-Z]?|V-\d+[A-Z]?|PSV-\d+[A-Z]?)\b", re.IGNORECASE)
_BREAKER_PATTERN = re.compile(r"\b(MCC-\d+[A-Z]?-\d+|BKR-\d+[A-Z]?|SWG-\d+[A-Z]?)\b", re.IGNORECASE)


class PermitEngine:
    """Drafts industrial permits, performs missing parameter analysis, and grounds evidence."""

    def __init__(
        self,
        cov_verifier: ChainOfVerification | None = None,
    ) -> None:
        self._cov = cov_verifier or ChainOfVerification()

    def draft_permit(
        self,
        permit_type: PermitType,
        work_description: str,
        equipment_tag: str | None = None,
        facility_name: str = "Industrial Processing Plant",
        unit_area: str = "Process Area 1",
        work_order_number: str = "WO-AUTO-01",
        context_chunks: list[Any] | None = None,
    ) -> IndustrialPermit:
        """Generate a structured, evidence-grounded industrial permit draft."""
        # 1. Resolve equipment tag
        detected_tags = _EQUIPMENT_TAG_PATTERN.findall(work_description)
        resolved_tag = equipment_tag or (detected_tags[0] if detected_tags else "")

        # 2. Extract potential valves and electrical breakers for isolation
        detected_valves = _VALVE_PATTERN.findall(work_description)
        detected_breakers = _BREAKER_PATTERN.findall(work_description)

        # Also search context chunks if available
        if context_chunks:
            for chk in context_chunks:
                txt = chk.get("text", "") if isinstance(chk, dict) else getattr(chk, "text", "")
                for v in _VALVE_PATTERN.findall(txt):
                    if v not in detected_valves:
                        detected_valves.append(v)
                for b in _BREAKER_PATTERN.findall(txt):
                    if b not in detected_breakers:
                        detected_breakers.append(b)

        # 3. Build isolation points
        isolation_points: list[IsolationPoint] = []
        for v in detected_valves:
            isolation_points.append(
                IsolationPoint(
                    tag=v.upper(),
                    isolation_type="Process Valve",
                    status="Closed, Locked, Tagged",
                    location=f"{unit_area} Piping",
                )
            )
        for b in detected_breakers:
            isolation_points.append(
                IsolationPoint(
                    tag=b.upper(),
                    isolation_type="Electrical Breaker",
                    status="Racked Out, Padlock Applied, Tagged",
                    location="Substation MCC",
                )
            )

        # 4. Set template defaults based on permit classification
        title = f"{permit_type.value.replace('_', ' ').title()} Permit"
        hazards: list[str] = []
        precautions: list[str] = []
        ppe: list[str] = ["Hard Hat", "Safety Glasses with Side Shields", "Steel-Toe Boots"]
        missing_info: list[str] = []
        gas_testing: GasTestingRequirements | None = None
        fire_watch = False
        standby_person = False

        if not resolved_tag:
            missing_info.append("Mandatory equipment tag is missing from request and documentation.")

        if permit_type == PermitType.HOT_WORK:
            title = "Hot Work & Flame Operations Permit"
            hazards.extend(["Atmospheric Flammability", "Thermal Burn / Sparks", "Combustible Fumes"])
            precautions.extend([
                "Continuous combustible gas monitoring (LEL < 10%).",
                "Remove combustible materials within 35 feet (11 meters).",
                "Designated Fire Watch stationed for duration + 30 minutes post-work.",
                "Multi-purpose ABC Fire Extinguisher stationed on site.",
            ])
            ppe.extend(["Welding Helmet / Cutting Goggles", "Flame-Resistant Clothing (FRC)", "Heavy Leather Work Gloves"])
            gas_testing = GasTestingRequirements(lel_max_percent=10.0, oxygen_min_percent=19.5, oxygen_max_percent=23.5)
            fire_watch = True

        elif permit_type == PermitType.CONFINED_SPACE_ENTRY:
            title = "Confined Space Entry Permit"
            hazards.extend(["Oxygen Deficiency / Enrichment", "Toxic Gas Accumulation (H2S, CO)", "Engulfment Hazard", "Restricted Egress"])
            precautions.extend([
                "Continuous forced mechanical ventilation.",
                "Calibrated 4-gas atmospheric testing prior to and during entry.",
                "Dedicated Trained Standby Entrant Attendant stationed outside entry point.",
                "Retrieval tripod, harness, and lifeline attached to entrant.",
                "Positive isolation (blinds/disconnects) of all process lines.",
            ])
            ppe.extend(["Full Body Harness", "Personal 4-Gas Monitor", "Chemical Splash / Impervious Coveralls"])
            gas_testing = GasTestingRequirements(
                oxygen_min_percent=19.5,
                oxygen_max_percent=23.5,
                lel_max_percent=10.0,
                h2s_max_ppm=10.0,
                co_max_ppm=25.0,
            )
            standby_person = True

            if not isolation_points:
                missing_info.append("Confined space requires verified positive isolation (blinds or disconnects).")

        elif permit_type == PermitType.LOCKOUT_TAGOUT:
            title = "Lockout / Tagout (LOTO) Energy Isolation Permit"
            hazards.extend(["High Voltage Arc Flash", "Residual Hydraulic / Pneumatic Pressure", "Unexpected Machine Start"])
            precautions.extend([
                "Zero Energy State verification: Attempt restart after lockout.",
                "Individual standardized padlocks and danger tags attached by each craftsperson.",
                "Depressurize and bleed trapped fluid/pneumatic lines.",
            ])
            ppe.extend(["NFPA 70E Arc Flash Shield", "Dielectric Insulated Gloves", "Hearing Protection"])
            if not isolation_points:
                missing_info.append("No verified valve or breaker isolation points identified.")

        elif permit_type == PermitType.COLD_WORK:
            title = "Cold Work & Mechanical Maintenance Permit"
            hazards.extend(["Pressurized Fluid Release", "Pinch Points", "Chemical Residue"])
            precautions.extend([
                "Controlled line break procedure: Loosen bolts away from body first.",
                "Verify zero pressure and ambient temperature prior to flange unbolting.",
                "Spill containment berm and absorbent pads positioned under piping break.",
            ])
            ppe.extend(["Nitrile Chemical Gloves", "Face Shield over Safety Glasses"])

        else:  # GENERAL_WORK
            title = "General Plant Work Permit"
            hazards.extend(["Slip, Trip, Fall", "Pinch Points", "Overhead Lifting"])
            precautions.extend([
                "Barricade work perimeter with warning tape.",
                "Daily pre-job toolbox safety briefing completed.",
                "Inspect all portable power tools and cords prior to use.",
            ])

        # 5. Create permit draft
        permit = IndustrialPermit(
            permit_type=permit_type,
            status=PermitStatus.DRAFT_GENERATED,
            title=title,
            work_order_number=work_order_number,
            facility_name=facility_name,
            unit_area=unit_area,
            equipment_tag=resolved_tag,
            equipment_description=f"Industrial equipment asset {resolved_tag}" if resolved_tag else "Unspecified Asset",
            work_description=work_description,
            hazards_identified=hazards,
            required_precautions=precautions,
            required_ppe=ppe,
            isolation_points=isolation_points,
            gas_testing=gas_testing,
            fire_watch_required=fire_watch,
            standby_personnel_required=standby_person,
            missing_information=missing_info,
        )

        # 6. Evidence Cross-Examination via CoV
        if context_chunks:
            # Flatten permit to dictionary for claim decomposition
            permit_fields_for_cov = {
                "equipment_tag": permit.equipment_tag,
                "work_description": permit.work_description,
                "hazards": permit.hazards_identified,
                "isolation_valves": [p.tag for p in permit.isolation_points],
                "gas_testing": permit.gas_testing.to_dict() if hasattr(permit.gas_testing, "to_dict") else (permit.gas_testing or {}),
            }
            ledger = self._cov.verify(permit_fields_for_cov, context_chunks, artifact_id=permit.permit_id)
            permit.evidence_ledger = ledger

            # Check if all claims are verified
            summary = ledger.summary()
            if summary["contradicted_claims"] > 0:
                permit.missing_information.append(
                    f"{summary['contradicted_claims']} claims contradicted by engineering documentation."
                )
                permit.status = PermitStatus.VERIFICATION_INCOMPLETE
            elif summary["unverified_claims"] > 0 or permit.missing_information:
                permit.status = PermitStatus.VERIFICATION_INCOMPLETE
            elif summary["all_verified"] and not permit.missing_information:
                permit.status = PermitStatus.READY_FOR_REVIEW
        else:
            # No context provided -> verification incomplete
            if permit.missing_information:
                permit.status = PermitStatus.VERIFICATION_INCOMPLETE
            else:
                permit.status = PermitStatus.DRAFT_GENERATED

        # CRITICAL SAFETY RULE: Under NO circumstances can permit status be set to AUTHORIZED_BY_HUMAN here
        if permit.status == PermitStatus.AUTHORIZED_BY_HUMAN:
            logger.error("Attempted unauthorized autonomous permit authorization. Resetting to DRAFT_GENERATED.")
            permit.status = PermitStatus.DRAFT_GENERATED

        return permit

    def to_markdown(self, permit: IndustrialPermit) -> str:
        """Render industrial permit as clean, professional Markdown representation."""
        lines = [
            f"# {permit.title.upper()}",
            f"**Permit ID:** {permit.permit_id} | **Status:** `{permit.status.value}`",
            f"**Facility:** {permit.facility_name} | **Unit / Area:** {permit.unit_area}",
            f"**Equipment Tag:** `{permit.equipment_tag or 'NONE'}` | **Work Order:** {permit.work_order_number}",
            f"**Drafted At:** {permit.created_at}",
            "",
            "## 1. SCOPE OF WORK",
            permit.work_description,
            "",
            "## 2. IDENTIFIED HAZARDS",
        ]
        for h in permit.hazards_identified:
            lines.append(f"- {h}")

        lines.extend(["", "## 3. MANDATORY SAFETY PRECAUTIONS"])
        for p in permit.required_precautions:
            lines.append(f"- {p}")

        lines.extend(["", "## 4. REQUIRED PERSONAL PROTECTIVE EQUIPMENT (PPE)"])
        for ppe in permit.required_ppe:
            lines.append(f"- {ppe}")

        if permit.gas_testing:
            lines.extend([
                "",
                "## 5. ATMOSPHERIC GAS TESTING LIMITS",
                f"- **Oxygen (O₂):** {permit.gas_testing.oxygen_min_percent}% - {permit.gas_testing.oxygen_max_percent}%",
                f"- **Combustible Gas (LEL):** Max {permit.gas_testing.lel_max_percent}%",
                f"- **Hydrogen Sulfide (H₂S):** Max {permit.gas_testing.h2s_max_ppm} ppm",
                f"- **Carbon Monoxide (CO):** Max {permit.gas_testing.co_max_ppm} ppm",
            ])

        if permit.isolation_points:
            lines.extend(["", "## 6. LOCKOUT / TAGOUT ISOLATION SCHEDULE"])
            lines.append("| Tag | Type | Required Status | Location |")
            lines.append("|---|---|---|---|")
            for iso in permit.isolation_points:
                lines.append(f"| `{iso.tag}` | {iso.isolation_type} | {iso.status} | {iso.location} |")

        if permit.missing_information:
            lines.extend(["", "## ⚠️ UNRESOLVED SAFETY GAPS / MISSING INFORMATION"])
            for m in permit.missing_information:
                lines.append(f"- **ALERT:** {m}")

        if permit.evidence_ledger:
            lines.extend([
                "",
                "## 7. EVIDENCE AUDIT LEDGER",
                f"Total Claims: {permit.evidence_ledger.summary()['total_claims']} | "
                f"Verified: {permit.evidence_ledger.summary()['verified_claims']} | "
                f"Unverified: {permit.evidence_ledger.summary()['unverified_claims']}",
            ])

        lines.extend([
            "",
            "---",
            "### HUMAN AUTHORIZATION & SIGN-OFF",
            "> **NOTICE:** This document was compiled with AI assistance. It DOES NOT constitute live operational authorization. "
            "An authorized plant supervisor or safety officer must physically verify isolation points and countersign below.",
            "",
            f"**Authorized By:** {permit.authorized_by or '_________________________ (Signature Required)'}",
            f"**Authorization Date:** {permit.authorized_at or '____-__-__ __:__'}",
        ])

        return "\n".join(lines)
