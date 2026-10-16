"""Unit tests for industrial permit drafting engine and template generation."""

import unittest
from permits.permit_engine import PermitEngine
from permits.permit_models import PermitStatus, PermitType
from verification.chain_of_verification import ChainOfVerification


class TestPermitEngine(unittest.TestCase):
    """Test suite for industrial permit models, templates, and drafting logic."""

    def setUp(self) -> None:
        self.cov = ChainOfVerification()
        self.engine = PermitEngine(cov_verifier=self.cov)
        self.sample_chunks = [
            {
                "chunk_id": "chk-101",
                "document_id": "doc-pump-sop",
                "page_index": 5,
                "text": "Pump P-101A overhaul requires closing isolation valve MOV-101A and racking out breaker MCC-4B-02.",
            },
            {
                "chunk_id": "chk-102",
                "document_id": "doc-hot-work-proc",
                "page_index": 1,
                "text": "Hot work on Pump P-101A requires combustible gas LEL to be strictly below 10%.",
            },
        ]

    def test_draft_hot_work_permit(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Perform welding on flange of pump P-101A. Close MOV-101A.",
            unit_area="Crude Distillation Unit",
            context_chunks=self.sample_chunks,
        )
        self.assertEqual(permit.permit_type, PermitType.HOT_WORK)
        self.assertEqual(permit.equipment_tag, "P-101A")
        self.assertTrue(permit.fire_watch_required)
        self.assertIsNotNone(permit.gas_testing)
        self.assertEqual(permit.gas_testing.lel_max_percent, 10.0)
        self.assertTrue(any("Welding" in p for p in permit.required_ppe))
        self.assertTrue(any(iso.tag == "MOV-101A" for iso in permit.isolation_points))
        self.assertIsNotNone(permit.evidence_ledger)
        self.assertNotEqual(permit.status, PermitStatus.AUTHORIZED_BY_HUMAN)

    def test_draft_confined_space_permit(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.CONFINED_SPACE_ENTRY,
            work_description="Internal vessel cleaning for vessel V-201. Close valve MOV-201A.",
        )
        self.assertEqual(permit.permit_type, PermitType.CONFINED_SPACE_ENTRY)
        self.assertEqual(permit.equipment_tag, "V-201")
        self.assertTrue(permit.standby_personnel_required)
        self.assertIsNotNone(permit.gas_testing)
        self.assertEqual(permit.gas_testing.oxygen_min_percent, 19.5)
        self.assertEqual(permit.gas_testing.oxygen_max_percent, 23.5)

    def test_draft_loto_permit(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.LOCKOUT_TAGOUT,
            work_description="Lockout pump P-101A. Close valve MOV-101A and rack out breaker MCC-4B-02.",
        )
        self.assertEqual(permit.permit_type, PermitType.LOCKOUT_TAGOUT)
        iso_tags = [iso.tag for iso in permit.isolation_points]
        self.assertIn("MOV-101A", iso_tags)
        self.assertIn("MCC-4B-02", iso_tags)

    def test_missing_equipment_tag_flags_gap(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.GENERAL_WORK,
            work_description="General cleaning and painting of structural steel.",
        )
        self.assertEqual(permit.equipment_tag, "")
        self.assertTrue(len(permit.missing_information) > 0)
        self.assertEqual(permit.status, PermitStatus.VERIFICATION_INCOMPLETE)

    def test_render_to_markdown(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld cracked support bracket on pump P-101A.",
        )
        md = self.engine.to_markdown(permit)
        self.assertIn("HOT WORK", md)
        self.assertIn("P-101A", md)
        self.assertIn("ATMOSPHERIC GAS TESTING", md)
        self.assertIn("HUMAN AUTHORIZATION", md)

    def test_never_autonomously_authorized(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.GENERAL_WORK,
            work_description="Inspect pump P-101A.",
            context_chunks=self.sample_chunks,
        )
        self.assertIn(permit.status, [PermitStatus.DRAFT_GENERATED, PermitStatus.VERIFICATION_INCOMPLETE, PermitStatus.READY_FOR_REVIEW])
        self.assertNotEqual(permit.status, PermitStatus.AUTHORIZED_BY_HUMAN)


if __name__ == "__main__":
    unittest.main()
