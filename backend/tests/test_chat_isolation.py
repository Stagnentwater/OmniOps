"""Integration and isolation tests for Chat Sessions ownership and user segregation."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from api.routes.chat import router as chat_router, get_chat_repo
from database.chat_repository import ChatMessage, ChatRepository, ChatSession
from database.user_repository import User
from dependencies import get_current_user


class TestChatIsolation(unittest.TestCase):
    """Test suite verifying chat session ownership isolation across users."""

    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(chat_router)

        self.mock_chat_repo = MagicMock(spec=ChatRepository)

        self.user_a = User(
            user_id="usr_alex_chen",
            email="alex.chen@refinery.internal",
            password_hash="hash_a",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.user_b = User(
            user_id="usr_elena_rostova",
            email="elena.rostova@refinery.internal",
            password_hash="hash_b",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Default authenticated user is User A
        self.current_user = self.user_a

        self.app.dependency_overrides[get_chat_repo] = lambda: self.mock_chat_repo
        self.app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_list_sessions_returns_only_authenticated_user_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        session_a1 = ChatSession(
            session_id="sess_a1",
            title="Heat Exchanger Troubleshooting",
            user_id=self.user_a.user_id,
            created_at=now,
            updated_at=now,
        )
        session_a2 = ChatSession(
            session_id="sess_a2",
            title="P-101 Pressure Diagnostics",
            user_id=self.user_a.user_id,
            created_at=now,
            updated_at=now,
        )

        self.mock_chat_repo.list_sessions.return_value = [session_a1, session_a2]

        response = self.client.get("/chat/sessions")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], "sess_a1")
        self.assertEqual(data[0]["user_id"], self.user_a.user_id)
        self.assertEqual(data[1]["id"], "sess_a2")

        # Verify repository was queried with User A's user_id
        self.mock_chat_repo.list_sessions.assert_called_once_with(user_id=self.user_a.user_id)

    def test_create_session_associates_authenticated_user_id(self) -> None:
        self.mock_chat_repo.create_session.return_value = "new_sess_123"

        response = self.client.post("/chat/sessions")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["session_id"], "new_sess_123")

        self.mock_chat_repo.create_session.assert_called_once_with(user_id=self.user_a.user_id)

    def test_get_session_messages_allowed_for_session_owner(self) -> None:
        now = datetime.now(timezone.utc)
        session_a = ChatSession(
            session_id="sess_a1",
            title="My Session",
            user_id=self.user_a.user_id,
            created_at=now,
            updated_at=now,
        )
        messages_a = [
            ChatMessage(
                message_id="msg_1",
                session_id="sess_a1",
                role="user",
                content="Why is pressure dropping?",
                citations=[],
                created_at=now,
                metadata={},
            )
        ]

        self.mock_chat_repo.get_session.return_value = session_a
        self.mock_chat_repo.get_messages.return_value = messages_a

        response = self.client.get("/chat/sessions/sess_a1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "Why is pressure dropping?")

    def test_get_session_messages_forbidden_for_different_user(self) -> None:
        now = datetime.now(timezone.utc)
        # Session belongs to User B
        session_b = ChatSession(
            session_id="sess_b1",
            title="Elena's Confidential Audit",
            user_id=self.user_b.user_id,
            created_at=now,
            updated_at=now,
        )

        self.mock_chat_repo.get_session.return_value = session_b

        # Current user is User A, requesting User B's session
        response = self.client.get("/chat/sessions/sess_b1")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Forbidden", response.json()["detail"])
        self.mock_chat_repo.get_messages.assert_not_called()

    def test_get_session_messages_not_found(self) -> None:
        self.mock_chat_repo.get_session.return_value = None

        response = self.client.get("/chat/sessions/nonexistent_session")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_session_allowed_for_owner(self) -> None:
        now = datetime.now(timezone.utc)
        session_a = ChatSession(
            session_id="sess_a1",
            title="Session to Delete",
            user_id=self.user_a.user_id,
            created_at=now,
            updated_at=now,
        )

        self.mock_chat_repo.get_session.return_value = session_a
        self.mock_chat_repo.delete_session.return_value = True

        response = self.client.delete("/chat/sessions/sess_a1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "deleted"})
        self.mock_chat_repo.delete_session.assert_called_once_with("sess_a1", user_id=self.user_a.user_id)

    def test_delete_session_forbidden_for_different_user(self) -> None:
        now = datetime.now(timezone.utc)
        session_b = ChatSession(
            session_id="sess_b1",
            title="User B Session",
            user_id=self.user_b.user_id,
            created_at=now,
            updated_at=now,
        )

        self.mock_chat_repo.get_session.return_value = session_b

        # User A attempts to delete User B's session
        response = self.client.delete("/chat/sessions/sess_b1")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.mock_chat_repo.delete_session.assert_not_called()

    def test_unauthenticated_chat_access_returns_401(self) -> None:
        # Re-create app without get_current_user override
        unauth_app = FastAPI()
        unauth_app.include_router(chat_router)
        unauth_client = TestClient(unauth_app)

        response = unauth_client.get("/chat/sessions")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
