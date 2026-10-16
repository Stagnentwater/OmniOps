"""Deterministic industrial safety and isolation validator for work permits."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from permits.permit_models import IndustrialPermit, PermitType

logger = logging.getLogger(__name__)

# Non-negotiable OSHA, NFPA & Indian Industrial (OISD-STD-105 / MRPL) plant boundary limits
OSHA_MIN_OXYGEN_PCT = 19.5       # Safe breathing floor (OISD-STD-105 Clause 5.1 & OSHA 1910.146)
OSHA_MAX_OXYGEN_PCT = 23.5       # Oxygen enrichment ceiling (OISD-STD-105 & OSHA)
OSHA_MAX_LEL_PCT = 10.0          # General safe ceiling for cold entry / general work
OISD_HOT_WORK_MAX_LEL_PCT = 1.0  # OISD-STD-105 Clause 4.2 / MRPL rule: 0.0% LEL hydrocarbon for hot work
OSHA_MAX_H2S_PPM = 10.0          # Maximum permissible H2S exposure ceiling (Factories Act & OSHA)
OSHA_MAX_CO_PPM = 25.0           # Maximum permissible CO exposure ceiling


@dataclass
class SafetyValidationResult:
    """Outcome of deterministic safety rules and energy isolation verification."""

    is_valid: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_controls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "violations": list(self.violations),
            "warnings": list(self.warnings),
            "recommended_controls": list(self.recommended_controls),
        }


class PermitSafetyValidator:
    """Enforces deterministic plant safety rules, gas boundaries, and LOTO compliance."""

    def validate(
        self,
        permit: IndustrialPermit,
        live_gas_readings: dict[str, float] | None = None,
    ) -> SafetyValidationResult:
        """Deterministically validate permit parameters against strict safety constraints."""
        violations: list[str] = []
        warnings: list[str] = []
        controls: list[str] = []

        # 1. Base mandatory asset requirements
        if not permit.equipment_tag:
            violations.append("SAFETY RULE VIOLATION: Permit must specify a confirmed equipment tag.")

        # 2. Check Gas Testing Boundaries
        if permit.gas_testing:
            gt = permit.gas_testing
            if gt.lel_max_percent > OSHA_MAX_LEL_PCT:
                violations.append(
                    f"SAFETY RULE VIOLATION: Flammable gas limit ({gt.lel_max_percent}% LEL) exceeds OSHA ceiling of {OSHA_MAX_LEL_PCT}%."
                )
            if gt.oxygen_min_percent < OSHA_MIN_OXYGEN_PCT:
                violations.append(
                    f"SAFETY RULE VIOLATION: Permissible minimum oxygen ({gt.oxygen_min_percent}%) below OSHA safe breathing floor of {OSHA_MIN_OXYGEN_PCT}%."
                )
            if gt.oxygen_max_percent > OSHA_MAX_OXYGEN_PCT:
                violations.append(
                    f"SAFETY RULE VIOLATION: Permissible maximum oxygen ({gt.oxygen_max_percent}%) exceeds OSHA enrichment ceiling of {OSHA_MAX_OXYGEN_PCT}%."
                )

        # 3. Check Live Gas Readings if supplied
        if live_gas_readings:
            if "lel" in live_gas_readings and live_gas_readings["lel"] > OSHA_MAX_LEL_PCT:
                violations.append(
                    f"ATMOSPHERIC HAZARD: Live combustible gas reading ({live_gas_readings['lel']}% LEL) exceeds safe limit ({OSHA_MAX_LEL_PCT}%). ENTRY PROHIBITED."
                )
            if "oxygen" in live_gas_readings:
                o2 = live_gas_readings["oxygen"]
                if o2 < OSHA_MIN_OXYGEN_PCT:
                    violations.append(
                        f"ATMOSPHERIC HAZARD: Live oxygen reading ({o2}%) is oxygen deficient (< {OSHA_MIN_OXYGEN_PCT}%). ENTRY PROHIBITED."
                    )
                elif o2 > OSHA_MAX_OXYGEN_PCT:
                    violations.append(
                        f"ATMOSPHERIC HAZARD: Live oxygen reading ({o2}%) is oxygen enriched (> {OSHA_MAX_OXYGEN_PCT}%). FLAMMABLE HAZARD."
                    )
            if "h2s" in live_gas_readings and live_gas_readings["h2s"] > OSHA_MAX_H2S_PPM:
                violations.append(
                    f"TOXIC GAS HAZARD: Live H2S reading ({live_gas_readings['h2s']} ppm) exceeds OSHA ceiling ({OSHA_MAX_H2S_PPM} ppm)."
                )
            if "co" in live_gas_readings and live_gas_readings["co"] > OSHA_MAX_CO_PPM:
                violations.append(
                    f"TOXIC GAS HAZARD: Live CO reading ({live_gas_readings['co']} ppm) exceeds OSHA ceiling ({OSHA_MAX_CO_PPM} ppm)."
                )

        # 4. Classification-Specific Deterministic Checks
        if permit.permit_type == PermitType.HOT_WORK:
            if not permit.fire_watch_required:
                violations.append("SAFETY RULE VIOLATION: Hot Work permits must mandatorily require a designated Fire Watch.")
            if not any("fire" in p.lower() or "spark" in p.lower() for p in permit.required_precautions):
                warnings.append("Advisory: Precaution list does not explicitly mention spark shields or fire extinguishers.")
            controls.append("Post-work 30-minute fire watch mandatory.")
            controls.append("OISD-STD-105: Continuous fire watch during work and mandatory 30-minute post-work monitoring.")

        elif permit.permit_type == PermitType.CONFINED_SPACE_ENTRY:
            if not permit.standby_personnel_required:
                violations.append("SAFETY RULE VIOLATION: Confined space entry mandates a dedicated Standby Entrant Attendant.")
            if not any("ventilat" in p.lower() for p in permit.required_precautions):
                violations.append("SAFETY RULE VIOLATION: Confined space entry requires forced mechanical ventilation.")
            if not any("harness" in p.lower() or "retrieval" in p.lower() for p in permit.required_ppe + permit.required_precautions):
                warnings.append("Advisory: Emergency retrieval harness or tripod not explicitly detailed.")
            controls.append("Continuous 4-gas atmospheric monitoring during occupancy.")
            controls.append("OISD-STD-105 / MRPL: Positive physical isolation (blinding/spading) of all inlet/outlet process nozzles required.")

        elif permit.permit_type == PermitType.LOCKOUT_TAGOUT:
            if not permit.isolation_points:
                violations.append("SAFETY RULE VIOLATION: LOTO permit cannot be approved without identified isolation points.")
            if not any("zero energy" in p.lower() or "restart" in p.lower() for p in permit.required_precautions):
                warnings.append("Advisory: Zero Energy verification test (try-step) should be emphasized in precautions.")
            controls.append("Each authorized employee must apply personal padlock and red danger tag.")

        elif permit.permit_type == PermitType.COLD_WORK:
            if not any("depressur" in p.lower() or "pressure" in p.lower() for p in permit.required_precautions):
                warnings.append("Advisory: Depressurization and line draining checks recommended prior to cold break.")

        is_valid = len(violations) == 0
        return SafetyValidationResult(
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
            recommended_controls=controls,
        )
