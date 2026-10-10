"""Integration and route tests for /profile endpoints."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from api.routes.profile import router as profile_router
from database.user_repository import User, UserProfile, UserRepository
from dependencies import get_auth_service, get_current_user, get_user_repo
from services.auth_service import AuthService


class TestProfileApiRoutes(unittest.TestCase):
    """Test suite for /profile GET and PUT endpoints."""

    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(profile_router)

        self.mock_user_repo = MagicMock(spec=UserRepository)
        self.auth_service = AuthService(
            secret_key="test-secret-key-for-profile-api-tests",
            algorithm="HS256",
            access_token_expire_minutes=60,
        )

        self.mock_current_user = User(
            user_id="usr_alex_123",
            email="alex.chen@refinery.internal",
            password_hash="mock_hash",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.app.dependency_overrides[get_user_repo] = lambda: self.mock_user_repo
        self.app.dependency_overrides[get_auth_service] = lambda: self.auth_service
        self.app.dependency_overrides[get_current_user] = lambda: self.mock_current_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    # ── GET /profile ─────────────────────────────────────────────────────────

    def test_get_profile_success(self) -> None:
        """Authenticated user successfully retrieves their own domain profile."""
        now = datetime.now(timezone.utc)
        self.mock_user_repo.get_profile.return_value = UserProfile(
            user_id="usr_alex_123",
            name="Alex Chen",
            skill_set=["Basic engineering", "Safety fundamentals"],
            designation="Graduate Trainee",
            refinery_experience_level="beginner",
            preferred_explanation_depth="detailed",
            created_at=now,
            updated_at=now,
        )

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["user_id"], "usr_alex_123")
        self.assertEqual(data["name"], "Alex Chen")
        self.assertEqual(data["designation"], "Graduate Trainee")
        self.assertEqual(data["refinery_experience_level"], "beginner")
        self.assertEqual(data["preferred_explanation_depth"], "detailed")
        self.assertEqual(data["skill_set"], ["Basic engineering", "Safety fundamentals"])
        self.mock_user_repo.get_profile.assert_called_once_with("usr_alex_123")

    def test_get_profile_not_found(self) -> None:
        """When profile does not exist in database, return 404 Not Found."""
        self.mock_user_repo.get_profile.return_value = None

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not found", response.json()["detail"].lower())

    # ── PUT /profile ─────────────────────────────────────────────────────────

    def test_update_profile_success(self) -> None:
        """Authenticated user updates their own profile successfully."""
        now = datetime.now(timezone.utc)
        updated_profile = UserProfile(
            user_id="usr_alex_123",
            name="Alexander Chen",
            skill_set=["Process Control", "Safety"],
            designation="Junior Engineer",
            refinery_experience_level="intermediate",
            preferred_explanation_depth="moderate",
            created_at=now,
            updated_at=now,
        )
        self.mock_user_repo.update_profile.return_value = updated_profile

        payload = {
            "name": "Alexander Chen",
            "designation": "Junior Engineer",
            "skill_set": ["Process Control", "Safety"],
            "refinery_experience_level": "intermediate",
            "preferred_explanation_depth": "moderate",
        }

        response = self.client.put("/profile", json=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["name"], "Alexander Chen")
        self.assertEqual(data["designation"], "Junior Engineer")
        self.assertEqual(data["refinery_experience_level"], "intermediate")
        self.assertEqual(data["preferred_explanation_depth"], "moderate")
        self.mock_user_repo.update_profile.assert_called_once_with(
            user_id="usr_alex_123",
            name="Alexander Chen",
            designation="Junior Engineer",
            skill_set=["Process Control", "Safety"],
            refinery_experience_level="intermediate",
            preferred_explanation_depth="moderate",
        )

    def test_update_profile_blank_name_fails(self) -> None:
        """Attempting to update name to empty whitespace fails with 422."""
        response = self.client.put("/profile", json={"name": "   "})
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("Name cannot be empty", response.json()["detail"])

    def test_update_profile_invalid_experience_level(self) -> None:
        """Invalid experience level fails with 422."""
        response = self.client.put(
            "/profile",
            json={"refinery_experience_level": "astronaut"},
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("Invalid experience level", response.json()["detail"])

    def test_update_profile_invalid_explanation_depth(self) -> None:
        """Invalid explanation depth fails with 422."""
        response = self.client.put(
            "/profile",
            json={"preferred_explanation_depth": "superficial"},
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("Invalid explanation depth", response.json()["detail"])

    # ── Ownership & Security Tests ───────────────────────────────────────────

    def test_unauthenticated_request_fails(self) -> None:
        """When get_current_user is not overridden, request without auth returns 401."""
        unauthenticated_app = FastAPI()
        unauthenticated_app.include_router(profile_router)
        unauthenticated_app.dependency_overrides[get_user_repo] = lambda: self.mock_user_repo
        unauthenticated_app.dependency_overrides[get_auth_service] = lambda: self.auth_service
        # Note: get_current_user is NOT overridden here, so standard Bearer validation applies

        client = TestClient(unauthenticated_app)
        get_res = client.get("/profile")
        self.assertEqual(get_res.status_code, status.HTTP_401_UNAUTHORIZED)

        put_res = client.put("/profile", json={"name": "Attacker"})
        self.assertEqual(put_res.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
