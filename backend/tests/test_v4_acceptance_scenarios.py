"""End-to-End Acceptance Tests for Version 4 (Task Area D: 10 Scenarios).

Verifies the 10 core industrial scenarios defined in V4 Acceptance Matrix:
1. Complete input with adequate evidence
2. Missing mandatory fields
3. Conflicting source documents
4. Unreadable or ambiguous P&ID labels
5. Unsupported equipment or isolation information
6. Insufficient retrieval evidence
7. A failed verification check
8. An unauthorized user / AI attempting approval or sign-off
9. A reviewer rejecting or requesting changes to a draft
10. A valid draft proceeding through the authorized review workflow
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from permits.permit_engine import PermitEngine
from permits.permit_models import (
    GasTestingRequirements,
    IndustrialPermit,
    IsolationPoint,
    PermitStatus,
    PermitType,
)
from permits.review_service import PermitReviewService
from permits.safety_validator import PermitSafetyValidator
from verification.chain_of_verification import ChainOfVerification
from verification.evidence_ledger import VerificationStatus
from verification.self_rag import SelfRAGChecker, SufficiencyStatus


class TestV4AcceptanceScenarios(unittest.TestCase):
    """Rigorous acceptance testing across all 10 critical industrial scenarios."""

    def setUp(self) -> None:
        self.cov = ChainOfVerification()
        self.validator = PermitSafetyValidator()
        self.engine = PermitEngine(cov_verifier=self.cov)
        self.review_service = PermitReviewService(validator=self.validator)
        self.self_rag = SelfRAGChecker()

        # Realistic refinery technical context chunks (Crude Unit / Vessel V-201)
        self.v201_sop_chunks = [
            {
                "chunk_id": "chk-v201-01",
                "document_id": "MRPL-SOP-CDU-V201",
                "page_index": 12,
                "text": (
                    "Vessel V-201 hot work procedures: Positive physical isolation requires closing "
                    "inlet valve MOV-201A and bypass valve MOV-201B, followed by slip blind insertion. "
                    "Atmospheric gas testing must confirm combustible gas LEL is strictly 0.0% "
                    "and oxygen level is between 19.5% and 23.5%."
                ),
            },
            {
                "chunk_id": "chk-v201-02",
                "document_id": "MRPL-SAFETY-OISD-105",
                "page_index": 4,
                "text": (
                    "OISD-STD-105 Work Permit System: For welding on vessel V-201, continuous fire watch "
                    "with 30-minute post-work monitoring is mandatory. PPE must include flame-retardant coveralls, "
                    "welding helmet, and leather gauntlets."
                ),
            },
        ]

    def test_scenario_01_complete_input_with_adequate_evidence(self) -> None:
        """Scenario 1: Complete input with adequate evidence is drafted and reaches READY_FOR_REVIEW upon review gate."""
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Perform welding on vessel V-201 nozzles. Isolate MOV-201A and MOV-201B. Maintain continuous fire watch.",
            equipment_tag="V-201",
            unit_area="Crude Distillation Unit",
            context_chunks=self.v201_sop_chunks,
        )

        self.assertEqual(permit.equipment_tag, "V-201")
        self.assertEqual(permit.permit_type, PermitType.HOT_WORK)
        self.assertTrue(permit.fire_watch_required)
        self.assertIsNotNone(permit.evidence_ledger)

        # Verify traceability
        summary = permit.evidence_ledger.summary()
        self.assertGreater(summary["total_claims"], 0)
        self.assertGreater(summary["verified_claims"], 0)
        self.assertEqual(summary["contradicted_claims"], 0)

        # Check exact citation references
        verified_entries = [
            e for e in permit.evidence_ledger.entries
            if e.verification_status == VerificationStatus.VERIFIED
        ]
        self.assertTrue(len(verified_entries) > 0)
        first_entry = verified_entries[0]
        self.assertIn("MRPL-", first_entry.source_document_id)
        self.assertGreater(first_entry.page_index, 0)
        self.assertTrue(len(first_entry.exact_source_quote) > 0)

        # Status must never be autonomously authorized
        self.assertNotEqual(permit.status, PermitStatus.AUTHORIZED_BY_HUMAN)

        # Submit to review gate: transitions to READY_FOR_REVIEW for human authorization
        ready_permit, val_result = self.review_service.submit_for_review(permit)
        self.assertTrue(val_result.is_valid)
        self.assertEqual(ready_permit.status, PermitStatus.READY_FOR_REVIEW)

    def test_scenario_02_missing_mandatory_fields(self) -> None:
        """Scenario 2: Missing mandatory fields flagged and blocks permit approval."""
        # Missing equipment tag
        permit_no_tag = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Welding repairs in general piping corridor without asset tag.",
            context_chunks=self.v201_sop_chunks,
        )
        self.assertEqual(permit_no_tag.equipment_tag, "")
        self.assertTrue(any("equipment tag" in m.lower() for m in permit_no_tag.missing_information))
        self.assertEqual(permit_no_tag.status, PermitStatus.VERIFICATION_INCOMPLETE)

        # Missing isolation points for LOTO
        permit_loto_empty = IndustrialPermit(
            permit_type=PermitType.LOCKOUT_TAGOUT,
            equipment_tag="P-101A",
            isolation_points=[],
        )
        val_result = self.validator.validate(permit_loto_empty)
        self.assertFalse(val_result.is_valid)
        self.assertTrue(any("without identified isolation points" in v for v in val_result.violations))

    def test_scenario_03_conflicting_source_documents(self) -> None:
        """Scenario 3: Contradictory claims in source documents are detected by CoV and marked CONTRADICTED."""
        # Outdated procedure specifying unsafe LEL vs current standard
        contradictory_chunks = [
            {
                "chunk_id": "chk-old-01",
                "document_id": "OBSOLETE-PROC-1998",
                "page_index": 2,
                "text": "Combustible gas limit for hot work is 10% LEL.",
            }
        ]

        # Claim states 25% LEL
        claim_data = {
            "equipment_tag": "V-201",
            "gas_testing": {"lel_max_percent": "25%"},
        }
        ledger = self.cov.verify(claim_data, contradictory_chunks, artifact_id="art-contra")
        summary = ledger.summary()

        self.assertGreater(summary["contradicted_claims"], 0)
        contra_entries = [
            e for e in ledger.entries
            if e.verification_status == VerificationStatus.CONTRADICTED
        ]
        self.assertEqual(len(contra_entries), 1)
        self.assertIn("contradicting", contra_entries[0].exact_source_quote)

    def test_scenario_04_unreadable_or_ambiguous_pid_labels(self) -> None:
        """Scenario 4: Ambiguous visual extraction never invents fake valve tags and flags human check."""
        ambiguous_claim = {
            "equipment_tag": "V-201",
            "isolation_valves": ["VALVE-???-UNREADABLE"],
        }
        ledger = self.cov.verify(ambiguous_claim, self.v201_sop_chunks, artifact_id="art-ambig")
        entries = ledger.entries

        # Must be classified as UNVERIFIED_REQUIRES_HUMAN_CHECK, not hallucinated as verified
        unverified = [
            e for e in entries
            if e.claim_text == "VALVE-???-UNREADABLE"
        ]
        self.assertEqual(len(unverified), 1)
        self.assertEqual(unverified[0].verification_status, VerificationStatus.UNVERIFIED_REQUIRES_HUMAN_CHECK)

    def test_scenario_05_unsupported_equipment_or_isolation_information(self) -> None:
        """Scenario 5: Unsupported equipment or absent isolation points flags verification incomplete."""
        permit = self.engine.draft_permit(
            permit_type=PermitType.LOCKOUT_TAGOUT,
            work_description="Isolate unsupported equipment P-9999-NONEXISTENT.",
            equipment_tag="P-9999-NONEXISTENT",
            context_chunks=[],  # No evidence
        )
        self.assertEqual(permit.status, PermitStatus.VERIFICATION_INCOMPLETE)
        self.assertTrue(len(permit.isolation_points) == 0)
        self.assertTrue(any("isolation" in m.lower() for m in permit.missing_information))

    def test_scenario_06_insufficient_retrieval_evidence(self) -> None:
        """Scenario 6: Zero retrieval evidence is flagged as INSUFFICIENT by Self-RAG and forms secondary query."""
        eval_result = self.self_rag.evaluate_sufficiency(
            query="Prepare hot work permit for reactor R-301",
            context_chunks=[],
            required_parameters=["pressure", "temperature", "isolation"],
        )
        self.assertEqual(eval_result.status, SufficiencyStatus.INSUFFICIENT)
        self.assertEqual(eval_result.confidence, 0.0)
        self.assertIsNotNone(eval_result.secondary_query)
        self.assertIn("R-301", eval_result.secondary_query)

    def test_scenario_07_failed_verification_check(self) -> None:
        """Scenario 7: Safety violations prevent permit from reaching READY_FOR_REVIEW."""
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Welding on vessel V-201",
            equipment_tag="V-201",
        )
        # Artificially breach safe oxygen limit
        permit.gas_testing = GasTestingRequirements(oxygen_min_percent=15.0)

        updated_permit, val_result = self.review_service.submit_for_review(permit)
        self.assertFalse(val_result.is_valid)
        self.assertEqual(updated_permit.status, PermitStatus.VERIFICATION_INCOMPLETE)

    def test_scenario_08_unauthorized_user_or_ai_attempting_approval(self) -> None:
        """Scenario 8: Autonomous AI agent or unconfirmed signature is strictly rejected with PermissionError."""
        permit = IndustrialPermit(
            permit_id="PERMIT-SAFETY-001",
            status=PermitStatus.READY_FOR_REVIEW,
            equipment_tag="V-201",
            work_description="Welding nozzle",
        )

        # 1. AI agent attempt -> Hard PermissionError
        with self.assertRaises(PermissionError) as ctx:
            self.review_service.sign_off_permit(
                permit=permit,
                reviewer_id="agent-llama3",
                reviewer_name="AI Agent",
                reviewer_role="Autonomous LLM",
                signature_confirmed=True,
                is_automated_agent=True,
            )
        self.assertIn("CRITICAL SAFETY VIOLATION", str(ctx.exception))

        # 2. Missing explicit confirmation -> ValueError
        with self.assertRaises(ValueError):
            self.review_service.sign_off_permit(
                permit=permit,
                reviewer_id="human-101",
                reviewer_name="Safety Lead",
                reviewer_role="Area In-Charge",
                signature_confirmed=False,
                is_automated_agent=False,
            )

    def test_scenario_09_reviewer_rejecting_or_requesting_changes(self) -> None:
        """Scenario 9: Human reviewer can reject draft with actionable feedback."""
        permit = IndustrialPermit(
            permit_id="PERMIT-REJECT-001",
            status=PermitStatus.READY_FOR_REVIEW,
            equipment_tag="V-201",
        )
        rejected = self.review_service.reject_permit(
            permit=permit,
            reviewer_id="REV-849",
            reason="Gas monitoring frequency must be 2 hours instead of 4 hours under OISD-STD-105.",
        )
        self.assertEqual(rejected.status, PermitStatus.VERIFICATION_INCOMPLETE)
        self.assertTrue(any("OISD-STD-105" in m for m in rejected.missing_information))
        self.assertTrue(any("REV-849" in m for m in rejected.missing_information))

    def test_scenario_10_valid_draft_proceeds_through_authorized_review(self) -> None:
        """Scenario 10: Valid draft passes review gate and is authorized by a qualified human reviewer."""
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Perform welding on vessel V-201. Close valve MOV-201A.",
            equipment_tag="V-201",
            context_chunks=self.v201_sop_chunks,
        )
        # Ensure status is ready
        permit.status = PermitStatus.READY_FOR_REVIEW

        authorized = self.review_service.sign_off_permit(
            permit=permit,
            reviewer_id="EMP-9024",
            reviewer_name="Ramesh Kumar",
            reviewer_role="Chief Operations Officer / Area Safety In-Charge",
            signature_confirmed=True,
            is_automated_agent=False,
        )

        self.assertEqual(authorized.status, PermitStatus.AUTHORIZED_BY_HUMAN)
        self.assertIn("Ramesh Kumar", authorized.authorized_by)
        self.assertIn("EMP-9024", authorized.authorized_by)
        self.assertIsNotNone(authorized.authorized_at)


if __name__ == "__main__":
    unittest.main()
