"""Unit tests for deterministic industrial safety and isolation validator."""

import unittest
from permits.permit_engine import PermitEngine
from permits.permit_models import (
    GasTestingRequirements,
    IndustrialPermit,
    PermitType,
)
from permits.safety_validator import PermitSafetyValidator


class TestPermitSafetyValidator(unittest.TestCase):
    """Test suite for deterministic safety rule checks and gas boundary limits."""

    def setUp(self) -> None:
        self.validator = PermitSafetyValidator()
        self.engine = PermitEngine()

    def test_valid_hot_work_permit(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        result = self.validator.validate(permit)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.violations), 0)

    def test_hot_work_missing_fire_watch_violation(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        permit.fire_watch_required = False  # Artificially remove fire watch
        result = self.validator.validate(permit)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Fire Watch" in v for v in result.violations))

    def test_excessive_lel_specification_violation(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        permit.gas_testing = GasTestingRequirements(lel_max_percent=25.0)
        result = self.validator.validate(permit)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("exceeds OSHA ceiling" in v for v in result.violations))

    def test_live_gas_reading_hazard(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        # Supply dangerous live gas readings
        readings = {"lel": 18.5, "oxygen": 18.2, "h2s": 15.0}
        result = self.validator.validate(permit, live_gas_readings=readings)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Live combustible gas reading" in v for v in result.violations))
        self.assertTrue(any("oxygen deficient" in v for v in result.violations))
        self.assertTrue(any("Live H2S reading" in v for v in result.violations))

    def test_confined_space_missing_ventilation_violation(self) -> None:
        permit = IndustrialPermit(
            permit_type=PermitType.CONFINED_SPACE_ENTRY,
            equipment_tag="TK-101",
            standby_personnel_required=True,
            required_precautions=["Basic check"],  # No ventilation mentioned
        )
        result = self.validator.validate(permit)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("forced mechanical ventilation" in v for v in result.violations))

    def test_loto_empty_isolation_points_violation(self) -> None:
        permit = IndustrialPermit(
            permit_type=PermitType.LOCKOUT_TAGOUT,
            equipment_tag="P-101A",
            isolation_points=[],  # Empty isolation points
        )
        result = self.validator.validate(permit)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("cannot be approved without identified isolation points" in v for v in result.violations))


if __name__ == "__main__":
    unittest.main()
