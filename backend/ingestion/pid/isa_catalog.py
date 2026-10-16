"""ISA 5.1 Standard Catalog and Refinery Compliance Verification.

Defines the ANSI/ISA-5.1-2009 standard instrumentation and equipment
identification specifications for industrial refinery P&ID drawings.
Identifies whether a symbol or tag complies with standard ISA 5.1 or
represents a refinery-specific proprietary/custom non-standard symbol
requiring operator localization and human review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# ANSI/ISA-5.1 Standard First Letters (Measured / Initiating Variables)
# ---------------------------------------------------------------------------
ISA_FIRST_LETTERS: Final[dict[str, str]] = {
    "A": "Analysis",
    "B": "Burner / Combustion",
    "C": "User's Choice",
    "D": "Density / Specific Gravity",
    "E": "Voltage",
    "F": "Flow Rate",
    "G": "Gauging / Dimensional",
    "H": "Manual Operation",
    "I": "Current (Electrical)",
    "J": "Power",
    "K": "Time / Time Schedule",
    "L": "Level",
    "M": "Moisture / Humidity",
    "N": "User's Choice",
    "O": "User's Choice",
    "P": "Pressure / Vacuum",
    "Q": "Quantity / Totalizer",
    "R": "Radiation",
    "S": "Speed / Frequency",
    "T": "Temperature",
    "U": "Multivariable",
    "V": "Vibration / Mechanical Analysis",
    "W": "Weight / Force",
    "X": "Unclassified",
    "Y": "Event / State",
    "Z": "Position / Dimension",
}

# ---------------------------------------------------------------------------
# ANSI/ISA-5.1 Standard Succeeding Letters (Readout / Output / Modifier)
# ---------------------------------------------------------------------------
ISA_SUCCEEDING_LETTERS: Final[dict[str, str]] = {
    "A": "Alarm",
    "C": "Controller",
    "D": "Differential",
    "E": "Sensor / Primary Element",
    "F": "Ratio (Fraction)",
    "G": "Glass / Viewing Device",
    "H": "High",
    "I": "Indicator",
    "L": "Low",
    "M": "Middle / Intermediate",
    "O": "Orifice / Restriction",
    "P": "Point (Test Point)",
    "Q": "Integrate / Totalize",
    "R": "Record",
    "S": "Switch",
    "T": "Transmit",
    "V": "Valve / Damper / Louver",
    "W": "Well",
    "X": "Unclassified",
    "Y": "Relay / Compute / Convert",
    "Z": "Driver / Actuator / Final Control Element",
}

# ---------------------------------------------------------------------------
# Standard Refinery Equipment Code Prefixes (ISA / Process Industry Norms)
# ---------------------------------------------------------------------------
STANDARD_EQUIPMENT_PREFIXES: Final[dict[str, str]] = {
    "P": "Pump",
    "C": "Compressor",
    "K": "Blower / Turbine",
    "E": "Heat Exchanger / Reboiler / Condenser",
    "HE": "Heat Exchanger",
    "H": "Fired Heater / Furnace",
    "F": "Furnace / Filter",
    "V": "Pressure Vessel / Flash Drum",
    "D": "Drum / Vessel",
    "T": "Tower / Distillation Column",
    "COL": "Distillation Column",
    "TK": "Atmospheric Storage Tank",
    "R": "Chemical Reactor",
    "FL": "Flare Stack",
    "AG": "Agitator / Mixer",
    "ST": "Steam Turbine",
    "B": "Boiler / Steam Generator",
}

# ---------------------------------------------------------------------------
# Standard ISA 5.1 Graphic Symbol Classification Names
# ---------------------------------------------------------------------------
STANDARD_ISA_SYMBOLS: Final[frozenset[str]] = frozenset({
    "gate_valve",
    "globe_valve",
    "ball_valve",
    "butterfly_valve",
    "check_valve",
    "needle_valve",
    "plug_valve",
    "angle_valve",
    "diaphragm_valve",
    "safety_valve",
    "relief_valve",
    "pressure_safety_valve",
    "pressure_relief_valve",
    "control_valve",
    "solenoid_valve",
    "motor_operated_valve",
    "centrifugal_pump",
    "positive_displacement_pump",
    "reciprocating_compressor",
    "centrifugal_compressor",
    "shell_and_tube_heat_exchanger",
    "heat_exchanger",
    "air_cooler",
    "fin_fan_cooler",
    "storage_tank",
    "vertical_vessel",
    "horizontal_vessel",
    "distillation_column",
    "orifice_plate",
    "rotameter",
    "venturi_tube",
    "magnetic_flowmeter",
    "coriolis_meter",
    "thermowell",
    "strainer",
    "blind_flange",
    "spectacle_blind",
    "reducer",
    "pressure_transmitter",
    "temperature_transmitter",
    "flow_transmitter",
    "level_transmitter",
    "pressure_indicator",
    "temperature_indicator",
    "flow_indicator",
    "level_indicator",
    "instrument_bubble",
})

# ---------------------------------------------------------------------------
# Standard ISA 5.1 Instrument Loop Prefixes
# ---------------------------------------------------------------------------
STANDARD_ISA_LOOP_PREFIXES: Final[frozenset[str]] = frozenset({
    # Pressure
    "PT", "PI", "PC", "PV", "PCV", "PSV", "PRV", "PS", "PA", "PDT", "PDI", "PDC", "PDV",
    # Temperature
    "TT", "TI", "TC", "TV", "TCV", "TS", "TA", "TW", "TE", "TDT", "TDI", "TDC", "TDV",
    # Flow
    "FT", "FI", "FC", "FV", "FCV", "FS", "FA", "FE", "FIT", "FIC", "FO", "FR",
    # Level
    "LT", "LI", "LC", "LV", "LCV", "LS", "LA", "LG", "LSH", "LSL", "LIT", "LIC",
    # Analytical
    "AT", "AI", "AC", "AV", "AS", "AA", "AE",
    # Safety / Emergency / Valve Actuation
    "HV", "HS", "HA", "XV", "SDV", "BDV", "ESD", "ZT", "ZS",
    # Vibration / Speed
    "VT", "VI", "VA", "VS", "ST", "SI", "SC",
})

# ---------------------------------------------------------------------------
# Explicit Non-ISA 5.1 Proprietary / Custom Refinery Symbols
# ---------------------------------------------------------------------------
KNOWN_NON_ISA_SYMBOLS: Final[frozenset[str]] = frozenset({
    "proprietary_vendor_valve",
    "custom_valve",
    "specialty_valve",
    "pig_launcher",
    "pig_receiver",
    "sampling_station",
    "flame_arrestor",
    "injection_quill",
    "desuperheater",
    "vendor_skid",
    "custom_interlock",
    "unknown_symbol",
    "non_standard_symbol",
    "rupture_disc_proprietary",
    "proprietary_multiport_valve",
    "magnetic_level_gauge_custom",
    "expansion_joint_custom",
    "hydraulic_actuator_custom",
})

# Regex for standard ISA tag patterns: e.g. PT-101, TT-102A, FV-304, P-101A, V-200
_TAG_FORMAT_REGEX = re.compile(r"^([A-Z]{1,6})-([0-9]{1,4}[A-Z]?)$")


@dataclass(frozen=True)
class ISACheckResult:
    """Result of validating an instrument/symbol against ISA 5.1 refinery standard."""

    is_standard: bool
    category: str
    details: str
    recommended_action: str


class ISA51Catalog:
    """Validator for ISA 5.1 compliance on industrial refinery drawings."""

    @classmethod
    def is_isa_standard_tag(cls, tag: str) -> ISACheckResult:
        """Validate whether a tag adheres to ANSI/ISA-5.1 or standard equipment syntax.

        Args:
            tag: Equipment or instrument tag string (e.g. 'PT-101', 'P-101', 'SP-99').

        Returns:
            ISACheckResult detailing compliance and classification.
        """
        clean_tag = tag.strip().upper()
        match = _TAG_FORMAT_REGEX.match(clean_tag)

        if not match:
            return ISACheckResult(
                is_standard=False,
                category="NON_CONFORMING_TAG_SYNTAX",
                details=f"Tag '{clean_tag}' does not follow standard ISA 5.1 hyphenated syntax (e.g., PT-101, P-101).",
                recommended_action="FLAG_FOR_HUMAN_CHECK",
            )

        prefix, number_suffix = match.groups()

        # Check if it is a standard equipment prefix (P, V, E, T, TK, etc.)
        if prefix in STANDARD_EQUIPMENT_PREFIXES:
            eq_name = STANDARD_EQUIPMENT_PREFIXES[prefix]
            return ISACheckResult(
                is_standard=True,
                category="EQUIPMENT",
                details=f"Standard equipment tag: {eq_name} ({prefix}-{number_suffix}).",
                recommended_action="AUTOMATED_CONFIRMATION",
            )

        # Check if it is a verified standard ISA 5.1 instrument loop prefix
        if prefix in STANDARD_ISA_LOOP_PREFIXES:
            first_meaning = ISA_FIRST_LETTERS.get(prefix[0], "Instrument")
            return ISACheckResult(
                is_standard=True,
                category="INSTRUMENT",
                details=f"Standard ISA 5.1 instrument: {first_meaning} ({prefix}-{number_suffix}).",
                recommended_action="AUTOMATED_CONFIRMATION",
            )

        # Tag has non-standard prefix (e.g. SP-99, VEND-01, HYD-V01, CUSTOM-1)
        return ISACheckResult(
            is_standard=False,
            category="NON_ISA_PROPRIETARY",
            details=f"Tag '{clean_tag}' uses non-standard prefix '{prefix}' outside refinery ISA 5.1 standard.",
            recommended_action="FLAG_FOR_HUMAN_CHECK",
        )

    @classmethod
    def is_isa_standard_symbol(
        cls,
        symbol_type: str,
        tag: str | None = None,
    ) -> ISACheckResult:
        """Validate whether a visual symbol type conforms to ISA 5.1 drawings.

        Args:
            symbol_type: Visual symbol classifier name (e.g., 'gate_valve', 'custom_valve').
            tag: Optional accompanying tag.

        Returns:
            ISACheckResult indicating whether the symbol is standard ISA 5.1.
        """
        clean_symbol = symbol_type.strip().lower().replace(" ", "_").replace("-", "_")

        # Explicit non-ISA symbol
        if clean_symbol in KNOWN_NON_ISA_SYMBOLS or "custom" in clean_symbol or "proprietary" in clean_symbol:
            return ISACheckResult(
                is_standard=False,
                category="NON_ISA_SYMBOL",
                details=f"Symbol '{symbol_type}' is recognized as proprietary/non-standard refinery hardware outside ISA 5.1.",
                recommended_action="FLAG_FOR_HUMAN_CHECK",
            )

        # Standard ISA symbol
        if clean_symbol in STANDARD_ISA_SYMBOLS:
            if tag:
                tag_check = cls.is_isa_standard_tag(tag)
                if not tag_check.is_standard:
                    return ISACheckResult(
                        is_standard=False,
                        category="NON_ISA_TAG_ON_STANDARD_SYMBOL",
                        details=f"Symbol shape '{symbol_type}' matches ISA 5.1, but associated tag '{tag}' is non-standard: {tag_check.details}",
                        recommended_action="FLAG_FOR_HUMAN_CHECK",
                    )
            return ISACheckResult(
                is_standard=True,
                category="STANDARD_ISA_SYMBOL",
                details=f"Symbol '{symbol_type}' fully conforms to ANSI/ISA-5.1 specification.",
                recommended_action="AUTOMATED_CONFIRMATION",
            )

        # Unknown / non-cataloged symbol
        return ISACheckResult(
            is_standard=False,
            category="UNKNOWN_NON_ISA_SYMBOL",
            details=f"Symbol '{symbol_type}' is not cataloged in standard ISA 5.1 symbols for this facility.",
            recommended_action="FLAG_FOR_HUMAN_CHECK",
        )
