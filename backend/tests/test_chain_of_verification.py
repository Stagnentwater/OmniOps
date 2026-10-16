"""Unit tests for Chain of Verification (CoV) and Evidence Ledger."""

import unittest
from verification.chain_of_verification import (
    ChainOfVerification,
    CoVClaim,
)
from verification.evidence_ledger import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    VerificationStatus,
)


class TestChainOfVerification(unittest.TestCase):
    """Test suite for CoV claim decomposition, verification, and ledger assembly."""

    def setUp(self) -> None:
        self.cov = ChainOfVerification()
        self.sample_chunks = [
            {
                "chunk_id": "chk-001",
                "document_id": "doc-sop-pump-01",
                "page_index": 4,
                "text": "Before servicing Pump P-101A, close suction isolation valve MOV-101A and lock breaker MCC-4B-02.",
            },
            {
                "chunk_id": "chk-002",
                "document_id": "doc-safety-rules",
                "page_index": 2,
                "text": "Atmospheric testing for hot work and confined spaces requires LEL to be strictly below 10%.",
            },
        ]

    def test_decompose_text(self) -> None:
        text = "Isolate valve MOV-101A before entering. Ensure pressure is below 50 psig."
        claims = self.cov.decompose_text(text)
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0].claim_id, "CLM-001")
        self.assertIn("MOV-101A", claims[0].claim_text)
        self.assertIn("MOV-101A", claims[0].verification_question)
        self.assertIn("50 psig", claims[1].claim_text)

    def test_decompose_permit_fields(self) -> None:
        permit_dict = {
            "equipment_tag": "P-101A",
            "isolation_valves": ["MOV-101A", "V-102"],
            "gas_testing": {"lel_max": "10%"},
        }
        claims = self.cov.decompose_permit_fields(permit_dict)
        self.assertTrue(len(claims) >= 3)
        tags = [c.claim_text for c in claims]
        self.assertIn("P-101A", tags)
        self.assertIn("MOV-101A", tags)

    def test_verify_claim_verified(self) -> None:
        claim = CoVClaim(
            claim_id="CLM-001",
            claim_text="Isolate valve MOV-101A and lock breaker MCC-4B-02.",
            field_name="isolation_points",
            verification_question="Is MOV-101A required for isolation?",
        )
        verified = self.cov.verify_claim(claim, self.sample_chunks)
        self.assertEqual(verified.status, VerificationStatus.VERIFIED)
        self.assertEqual(verified.chunk_id, "chk-001")
        self.assertEqual(verified.source_document_id, "doc-sop-pump-01")
        self.assertEqual(verified.page_index, 4)
        self.assertIn("MOV-101A", verified.exact_source_quote)

    def test_verify_claim_unverified(self) -> None:
        claim = CoVClaim(
            claim_id="CLM-999",
            claim_text="Verify that catalyst bed temperature is 450 °C.",
            field_name="process_parameters",
            verification_question="Is 450 °C catalyst temp verified?",
        )
        verified = self.cov.verify_claim(claim, self.sample_chunks)
        self.assertEqual(verified.status, VerificationStatus.UNVERIFIED_REQUIRES_HUMAN_CHECK)
        self.assertEqual(verified.exact_source_quote, "")

    def test_verify_claim_contradicted(self) -> None:
        claim = CoVClaim(
            claim_id="CLM-002",
            claim_text="Allow hot work if atmospheric LEL is below 25%.",
            field_name="gas_testing",
            verification_question="Is 25% LEL permissible?",
        )
        verified = self.cov.verify_claim(claim, self.sample_chunks)
        self.assertEqual(verified.status, VerificationStatus.CONTRADICTED)
        self.assertIn("10%", verified.reasoning)

    def test_full_ledger_generation(self) -> None:
        text = "Isolate pump MOV-101A. Check atmospheric LEL is 10%. Inspect unlisted valve V-999."
        ledger = self.cov.verify(text, self.sample_chunks, artifact_id="art-test-01")
        self.assertIsInstance(ledger, EvidenceLedger)
        self.assertEqual(ledger.artifact_id, "art-test-01")
        summary = ledger.summary()
        self.assertEqual(summary["total_claims"], 3)
        self.assertTrue(summary["verified_claims"] >= 1)
        self.assertTrue(summary["unverified_claims"] >= 1)
        self.assertFalse(summary["all_verified"])
        d = ledger.to_dict()
        self.assertIn("entries", d)
        self.assertIn("summary", d)


if __name__ == "__main__":
    unittest.main()
