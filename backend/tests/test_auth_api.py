"""Integration and route tests for /auth endpoints."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from api.routes.auth import router as auth_router
from database.user_repository import User, UserProfile, UserRepository
from dependencies import get_auth_service, get_current_user, get_user_repo
from services.auth_service import AuthService


class TestAuthApiRoutes(unittest.TestCase):
    """Test suite for FastAPI authentication routes."""

    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(auth_router)

        self.mock_user_repo = MagicMock(spec=UserRepository)
        self.auth_service = AuthService(
            secret_key="test-secret-key-32-bytes-long-for-testing",
            algorithm="HS256",
            access_token_expire_minutes=60,
        )

        self.app.dependency_overrides[get_user_repo] = lambda: self.mock_user_repo
        self.app.dependency_overrides[get_auth_service] = lambda: self.auth_service
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    # ── /auth/register ───────────────────────────────────────────────────────

    def test_register_success(self) -> None:
        """Registering a new plant user returns 201 and bearer token."""
        now = datetime.now(timezone.utc)
        self.mock_user_repo.get_user_by_email.return_value = None
        self.mock_user_repo.create_user.return_value = User(
            user_id="usr_alex_001",
            email="alex.chen@refinery.internal",
            password_hash="mock_hashed_pw",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        payload = {
            "email": "alex.chen@refinery.internal",
            "password": "SecurePassword123!",
            "name": "Alex Chen",
            "designation": "Graduate Trainee",
            "skill_set": ["Basic engineering", "Safety fundamentals"],
            "refinery_experience_level": "beginner",
            "preferred_explanation_depth": "detailed",
        }

        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["user_id"], "usr_alex_001")
        self.assertEqual(data["user"]["email"], "alex.chen@refinery.internal")
        self.assertEqual(data["user"]["name"], "Alex Chen")

        # Verify decoded token contains subject
        claims = self.auth_service.decode_access_token(data["access_token"])
        self.assertEqual(claims["sub"], "usr_alex_001")
        self.assertEqual(claims["email"], "alex.chen@refinery.internal")

    def test_register_duplicate_email(self) -> None:
        """Registering an existing email returns 409 Conflict."""
        now = datetime.now(timezone.utc)
        self.mock_user_repo.get_user_by_email.return_value = User(
            user_id="existing_usr",
            email="existing@refinery.internal",
            password_hash="pw",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        payload = {
            "email": "existing@refinery.internal",
            "password": "Password123",
            "name": "Jane",
        }

        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already exists", response.json()["detail"])

    def test_register_invalid_email(self) -> None:
        """Invalid email address fails validation with 422."""
        payload = {
            "email": "not-an-email",
            "password": "Password123",
            "name": "Jane",
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_register_short_password(self) -> None:
        """Password shorter than 6 characters fails validation with 422."""
        payload = {
            "email": "valid@refinery.internal",
            "password": "123",
            "name": "Jane",
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_register_invalid_experience_level(self) -> None:
        """Invalid experience level fails with 422."""
        payload = {
            "email": "valid@refinery.internal",
            "password": "Password123",
            "name": "Jane",
            "refinery_experience_level": "grandmaster",
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # ── /auth/login ──────────────────────────────────────────────────────────

    def test_login_success(self) -> None:
        """Correct credentials return 200 and access token."""
        now = datetime.now(timezone.utc)
        pwd_hash = self.auth_service.hash_password("CorrectPassword123!")

        self.mock_user_repo.get_user_by_email.return_value = User(
            user_id="usr_002",
            email="engineer@refinery.internal",
            password_hash=pwd_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.mock_user_repo.get_profile.return_value = UserProfile(
            user_id="usr_002",
            name="Marcus Vance",
            designation="Senior Process Engineer",
            refinery_experience_level="expert",
            preferred_explanation_depth="concise",
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "engineer@refinery.internal", "password": "CorrectPassword123!"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["user_id"], "usr_002")
        self.assertEqual(data["user"]["name"], "Marcus Vance")
        self.assertEqual(data["user"]["designation"], "Senior Process Engineer")

    def test_login_incorrect_password(self) -> None:
        """Incorrect password returns 401 Unauthorized."""
        now = datetime.now(timezone.utc)
        pwd_hash = self.auth_service.hash_password("CorrectPassword123!")

        self.mock_user_repo.get_user_by_email.return_value = User(
            user_id="usr_002",
            email="engineer@refinery.internal",
            password_hash=pwd_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "engineer@refinery.internal", "password": "WrongPassword!"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["detail"], "Invalid email or password")

    def test_login_nonexistent_email(self) -> None:
        """Nonexistent email returns 401 Unauthorized."""
        self.mock_user_repo.get_user_by_email.return_value = None

        response = self.client.post(
            "/auth/login",
            json={"email": "ghost@refinery.internal", "password": "AnyPassword"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["detail"], "Invalid email or password")

    # ── /auth/me ─────────────────────────────────────────────────────────────

    def test_me_success_with_valid_bearer_token(self) -> None:
        """Valid bearer token returns current user and domain profile."""
        now = datetime.now(timezone.utc)
        user = User(
            user_id="usr_003",
            email="lead@refinery.internal",
            password_hash="mock_hash",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.mock_user_repo.get_user_by_id.return_value = user
        self.mock_user_repo.get_profile.return_value = UserProfile(
            user_id="usr_003",
            name="Samantha Green",
            designation="Operations Lead",
            skill_set=["Distillation", "Safety"],
            refinery_experience_level="advanced",
            preferred_explanation_depth="moderate",
            created_at=now,
            updated_at=now,
        )

        token = self.auth_service.create_access_token(user_id="usr_003", email="lead@refinery.internal")

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["user_id"], "usr_003")
        self.assertEqual(data["email"], "lead@refinery.internal")
        self.assertEqual(data["profile"]["name"], "Samantha Green")
        self.assertEqual(data["profile"]["designation"], "Operations Lead")
        self.assertEqual(data["profile"]["refinery_experience_level"], "advanced")
        self.assertEqual(data["profile"]["skill_set"], ["Distillation", "Safety"])

    def test_me_unauthorized_without_header(self) -> None:
        """Calling /auth/me without Authorization header returns 401."""
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_unauthorized_with_tampered_token(self) -> None:
        """Calling /auth/me with a tampered token returns 401."""
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": "Bearer fake.tampered.token"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
