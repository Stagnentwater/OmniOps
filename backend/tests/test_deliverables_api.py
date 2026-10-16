"""Unit tests for /artifacts/my-deliverables endpoint (Deliverables Isolation & Persistence)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from api.routes.artifacts import router as artifacts_router, _PERMIT_CACHE
from database.user_repository import User
from dependencies import get_current_user
from permits.permit_models import IndustrialPermit, PermitStatus


class TestDeliverablesApiRoutes(unittest.TestCase):
    """Test suite for /artifacts/my-deliverables account-scoped endpoint."""

    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(artifacts_router)

        self.mock_user = User(
            user_id="usr_operator_77",
            email="operator77@refinery.internal",
            password_hash="mock_hash",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.app.dependency_overrides[get_current_user] = lambda: self.mock_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        _PERMIT_CACHE.clear()

    @patch("database.chat_repository.ChatRepository._connect")
    @patch("database.chat_repository.ChatRepository._ensure_tables")
    def test_my_deliverables_empty(self, mock_ensure: MagicMock, mock_connect: MagicMock) -> None:
        """User with no stored deliverables receives an empty list."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        response = self.client.get("/artifacts/my-deliverables")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    @patch("database.chat_repository.ChatRepository._connect")
    @patch("database.chat_repository.ChatRepository._ensure_tables")
    def test_my_deliverables_returns_persisted_artifacts_and_permits(
        self, mock_ensure: MagicMock, mock_connect: MagicMock
    ) -> None:
        """User receives properly mapped deliverable cards and permits."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "message_id": "msg_001",
                "session_id": "session_123",
                "session_title": "Session 123",
                "metadata": {
                    "artifact": {
                        "document_id": "doc_word_99",
                        "title": "Pump P-101A Handover SOP",
                        "file_name": "Pump_P101A_Handover.docx",
                        "format": "docx",
                        "file_size_bytes": 102400,
                    }
                },
                "created_at": "2026-10-12T10:00:00Z",
            },
            {
                "message_id": "msg_002",
                "session_id": "session_123",
                "session_title": "Session 123",
                "metadata": {
                    "permit": {
                        "permit_id": "PERMIT-V4-9999",
                        "title": "Hot Work Permit for Vessel V-201",
                        "equipment_tag": "V-201",
                        "facility_name": "Distillation Unit 2",
                        "status": "AUTHORIZED_BY_HUMAN",
                        "authorized_by": "Chief Safety Inspector",
                    }
                },
                "created_at": "2026-10-12T10:30:00Z",
            },
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        response = self.client.get("/artifacts/my-deliverables")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)

        # First item is DOCX
        doc_item = next(item for item in data if item["format"] == "docx")
        self.assertEqual(doc_item["title"], "Pump P-101A Handover SOP")
        self.assertEqual(doc_item["document_id"], "doc_word_99")
        self.assertEqual(doc_item["type"], "deliverable")

        # Second item is Permit
        permit_item = next(item for item in data if item["format"] == "permit")
        self.assertEqual(permit_item["title"], "Hot Work Permit for Vessel V-201")
        self.assertEqual(permit_item["permit_id"], "PERMIT-V4-9999")
        self.assertEqual(permit_item["equipment_tag"], "V-201")
        self.assertEqual(permit_item["status"], "AUTHORIZED_BY_HUMAN")
        self.assertEqual(permit_item["authorized_by"], "Chief Safety Inspector")

    @patch("database.chat_repository.ChatRepository._connect")
    @patch("database.chat_repository.ChatRepository._ensure_tables")
    def test_my_deliverables_includes_active_cache_permits(
        self, mock_ensure: MagicMock, mock_connect: MagicMock
    ) -> None:
        """Active memory-cached permits are seamlessly merged into user deliverables."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_conn
        mock_connect.return_value.__enter__.return_value = mock_conn

        cached_permit = IndustrialPermit(
            permit_id="PERMIT-ACTIVE-001",
            title="Live Cached Permit",
            work_order_number="WO-991",
            facility_name="Unit 1",
            equipment_tag="E-102",
            status=PermitStatus.READY_FOR_REVIEW,
        )
        _PERMIT_CACHE["PERMIT-ACTIVE-001"] = cached_permit

        response = self.client.get("/artifacts/my-deliverables")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Live Cached Permit")
        self.assertEqual(data[0]["permit_id"], "PERMIT-ACTIVE-001")
        self.assertEqual(data[0]["status"], "READY_FOR_REVIEW")

    def test_download_permit_direct_id_returns_docx(self) -> None:
        """Requesting /artifacts/PERMIT-BD9DD8F5/download generates and delivers a valid Word document."""
        response = self.client.get("/artifacts/PERMIT-BD9DD8F5/download")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn('filename="PERMIT-BD9DD8F5.docx"', response.headers["content-disposition"])
        self.assertTrue(len(response.content) > 1000)

    def test_download_permit_from_cache_returns_docx(self) -> None:
        """Cached permits are synthesized with full fields into downloadable .docx."""
        cached_permit = IndustrialPermit(
            permit_id="PERMIT-CACHED-777",
            title="Hot Work & Welding Permit",
            work_order_number="WO-WELD-99",
            facility_name="Crude Unit",
            equipment_tag="P-101A",
            status=PermitStatus.READY_FOR_REVIEW,
        )
        _PERMIT_CACHE["PERMIT-CACHED-777"] = cached_permit

        response = self.client.get("/artifacts/PERMIT-CACHED-777/download")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn('filename="PERMIT-CACHED-777.docx"', response.headers["content-disposition"])
        self.assertTrue(len(response.content) > 1000)


    def test_unauthenticated_request_rejected(self) -> None:
        """Unauthenticated user calling /artifacts/my-deliverables is rejected with 401 Unauthorized."""
        # Clear dependency override to test real auth enforcement
        self.app.dependency_overrides.clear()
        unauth_client = TestClient(self.app)
        response = unauth_client.get("/artifacts/my-deliverables")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("database.chat_repository.ChatRepository._connect")
    @patch("database.chat_repository.ChatRepository._ensure_tables")
    def test_cross_user_isolation_parameters(
        self, mock_ensure: MagicMock, mock_connect: MagicMock
    ) -> None:
        """Query for user deliverables isolates by current user's user_id."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        response = self.client.get("/artifacts/my-deliverables")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify query was executed with mock_user.user_id parameter
        call_args = mock_cursor.execute.call_args
        self.assertIsNotNone(call_args)
        query_sql, query_params = call_args[0]
        self.assertIn("s.user_id = %s", query_sql)
        self.assertEqual(query_params, (self.mock_user.user_id,))

    def test_sign_off_permit_endpoint_blocks_automated_agent(self) -> None:
        """Automated AI agent attempting to authorize permit via API is rejected with 403 Forbidden."""
        cached_permit = IndustrialPermit(
            permit_id="PERMIT-AUTO-BLOCK",
            title="Hot Work Permit",
            equipment_tag="V-201",
            status=PermitStatus.READY_FOR_REVIEW,
        )
        _PERMIT_CACHE["PERMIT-AUTO-BLOCK"] = cached_permit

        response = self.client.post(
            "/artifacts/permits/PERMIT-AUTO-BLOCK/sign-off",
            json={
                "reviewer_name": "Llama 3.2 Agent",
                "reviewer_role": "Autonomous System",
                "signature_confirmed": True,
                "is_automated_agent": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("CRITICAL SAFETY VIOLATION", response.json()["detail"])

    def test_sign_off_permit_endpoint_successful_human_authorization(self) -> None:
        """Authorized human reviewer successfully signs off permit via API."""
        cached_permit = IndustrialPermit(
            permit_id="PERMIT-HUMAN-OK",
            title="Hot Work Permit",
            equipment_tag="V-201",
            status=PermitStatus.READY_FOR_REVIEW,
        )
        _PERMIT_CACHE["PERMIT-HUMAN-OK"] = cached_permit

        response = self.client.post(
            "/artifacts/permits/PERMIT-HUMAN-OK/sign-off",
            json={
                "reviewer_name": "Senior Safety Lead",
                "reviewer_role": "Shift Operations Head",
                "signature_confirmed": True,
                "is_automated_agent": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["permit"]["status"], "AUTHORIZED_BY_HUMAN")
        self.assertIn("Senior Safety Lead", body["permit"]["authorized_by"])


if __name__ == "__main__":
    unittest.main()
