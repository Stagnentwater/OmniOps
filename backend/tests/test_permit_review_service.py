"""Unit tests for permit human review service and sign-off state machine."""

import unittest
from fastapi.testclient import TestClient
from main import app
from dependencies import get_current_user
from database.user_repository import User
from permits.permit_engine import PermitEngine
from permits.permit_models import IndustrialPermit, PermitStatus, PermitType
from permits.review_service import PermitReviewService
from api.routes.artifacts import register_permit


class TestPermitReviewService(unittest.TestCase):
    """Test suite for permit state machine, human sign-off gating, and AI blocking."""

    def setUp(self) -> None:
        from datetime import datetime, timezone
        self.review_service = PermitReviewService()
        self.engine = PermitEngine()
        now = datetime.now(timezone.utc)
        self.mock_user = User(
            user_id="user-eng-101",
            email="engineer@omniops.internal",
            password_hash="fake-hash",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def test_submit_for_review_success(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        updated, val_result = self.review_service.submit_for_review(permit)
        self.assertTrue(val_result.is_valid)
        self.assertEqual(updated.status, PermitStatus.READY_FOR_REVIEW)

    def test_submit_for_review_incomplete(self) -> None:
        permit = IndustrialPermit(
            permit_type=PermitType.GENERAL_WORK,
            equipment_tag="",  # Missing tag
            missing_information=["Missing tag"],
        )
        updated, val_result = self.review_service.submit_for_review(permit)
        self.assertEqual(updated.status, PermitStatus.VERIFICATION_INCOMPLETE)

    def test_human_sign_off_success(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        self.review_service.submit_for_review(permit)
        authorized = self.review_service.sign_off_permit(
            permit=permit,
            reviewer_id="USR-442",
            reviewer_name="David Miller",
            reviewer_role="Senior Plant Safety Officer",
            signature_confirmed=True,
            is_automated_agent=False,
        )
        self.assertEqual(authorized.status, PermitStatus.AUTHORIZED_BY_HUMAN)
        self.assertIn("David Miller", authorized.authorized_by)
        self.assertIsNotNone(authorized.authorized_at)

    def test_agent_sign_off_strictly_blocked(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        self.review_service.submit_for_review(permit)
        with self.assertRaises(PermissionError):
            self.review_service.sign_off_permit(
                permit=permit,
                reviewer_id="AGENT-AUTONOMOUS",
                reviewer_name="OmniOps AI Agent",
                reviewer_role="Autonomous LLM",
                signature_confirmed=True,
                is_automated_agent=True,  # AI agent attempt
            )

    def test_sign_off_missing_signature_raises(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        self.review_service.submit_for_review(permit)
        with self.assertRaises(ValueError):
            self.review_service.sign_off_permit(
                permit=permit,
                reviewer_id="USR-442",
                reviewer_name="David Miller",
                reviewer_role="Safety Officer",
                signature_confirmed=False,  # Missing signature confirmation
            )

    def test_sign_off_unready_permit_raises(self) -> None:
        permit = IndustrialPermit(
            permit_type=PermitType.HOT_WORK,
            status=PermitStatus.DRAFT_GENERATED,  # Not in READY_FOR_REVIEW
        )
        with self.assertRaises(ValueError):
            self.review_service.sign_off_permit(
                permit=permit,
                reviewer_id="USR-442",
                reviewer_name="David Miller",
                reviewer_role="Safety Officer",
                signature_confirmed=True,
            )

    def test_reject_permit(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        self.review_service.submit_for_review(permit)
        rejected = self.review_service.reject_permit(
            permit=permit,
            reviewer_id="USR-442",
            reason="Atmospheric gas testing calibration expired.",
        )
        self.assertEqual(rejected.status, PermitStatus.VERIFICATION_INCOMPLETE)
        self.assertTrue(any("Atmospheric gas testing calibration expired" in m for m in rejected.missing_information))

    def test_api_sign_off_endpoint(self) -> None:
        permit = self.engine.draft_permit(
            permit_type=PermitType.HOT_WORK,
            work_description="Weld pipeline flange on pump P-101A.",
        )
        self.review_service.submit_for_review(permit)
        register_permit(permit)

        app.dependency_overrides[get_current_user] = lambda: self.mock_user
        try:
            client = TestClient(app)

            # 1. Attempt autonomous agent sign-off -> 403 Forbidden
            resp = client.post(
                f"/artifacts/permits/{permit.permit_id}/sign-off",
                json={
                    "reviewer_name": "AI Agent",
                    "reviewer_role": "LLM",
                    "signature_confirmed": True,
                    "is_automated_agent": True,
                },
            )
            self.assertEqual(resp.status_code, 403)

            # 2. Legitimate human sign-off -> 200 OK
            resp_human = client.post(
                f"/artifacts/permits/{permit.permit_id}/sign-off",
                json={
                    "reviewer_name": "Sarah Jenkins",
                    "reviewer_role": "Plant Safety Lead",
                    "signature_confirmed": True,
                    "is_automated_agent": False,
                },
            )
            self.assertEqual(resp_human.status_code, 200)
            data = resp_human.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["permit"]["status"], "AUTHORIZED_BY_HUMAN")
        finally:
            app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    unittest.main()
