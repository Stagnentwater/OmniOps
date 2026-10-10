"""Unit tests for UserRepository and domain persona profile storage."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from database.user_repository import (
    User,
    UserProfile,
    UserRepository,
    VALID_EXPERIENCE_LEVELS,
    VALID_EXPLANATION_DEPTHS,
)


class TestUserRepositoryUnit(unittest.TestCase):
    """Dependency-free unit tests for UserRepository using mock database cursor."""

    def setUp(self) -> None:
        self.repo = UserRepository()

    def test_validation_constants(self) -> None:
        """Verify defined experience levels and explanation depths."""
        self.assertIn("beginner", VALID_EXPERIENCE_LEVELS)
        self.assertIn("intermediate", VALID_EXPERIENCE_LEVELS)
        self.assertIn("advanced", VALID_EXPERIENCE_LEVELS)
        self.assertIn("expert", VALID_EXPERIENCE_LEVELS)

        self.assertIn("concise", VALID_EXPLANATION_DEPTHS)
        self.assertIn("moderate", VALID_EXPLANATION_DEPTHS)
        self.assertIn("detailed", VALID_EXPLANATION_DEPTHS)

    def test_invalid_experience_level_raises_error(self) -> None:
        """Ensure invalid experience levels fail fast."""
        with self.assertRaises(ValueError) as ctx:
            self.repo.create_user(
                email="test@plant.com",
                password_hash="hash123",
                name="Test Engineer",
                refinery_experience_level="master",
            )
        self.assertIn("Invalid experience level", str(ctx.exception))

    def test_invalid_explanation_depth_raises_error(self) -> None:
        """Ensure invalid explanation depths fail fast."""
        with self.assertRaises(ValueError) as ctx:
            self.repo.create_user(
                email="test@plant.com",
                password_hash="hash123",
                name="Test Engineer",
                preferred_explanation_depth="infinite",
            )
        self.assertIn("Invalid explanation depth", str(ctx.exception))

    @patch.object(UserRepository, "_connect")
    def test_ensure_tables_executes_ddl(self, mock_connect: MagicMock) -> None:
        """Verify DDL execution creates users and user_profiles tables."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        self.repo._ensure_tables(mock_conn)

        executed_sql = " ".join(call.args[0] for call in mock_cursor.execute.call_args_list)
        self.assertIn("CREATE TABLE IF NOT EXISTS users", executed_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS user_profiles", executed_sql)
        self.assertIn("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_id", executed_sql)
        mock_conn.commit.assert_called_once()

    @patch.object(UserRepository, "_connect")
    def test_create_user_success(self, mock_connect: MagicMock) -> None:
        """Verify create_user inserts user identity and matching profile."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        user = self.repo.create_user(
            email="  ALEX.CHEN@Refinery.Internal  ",
            password_hash="hashed_pw_999",
            name="Alex Chen",
            designation="Graduate Trainee",
            skill_set=["Basic engineering", "Safety fundamentals"],
            refinery_experience_level="beginner",
            preferred_explanation_depth="detailed",
        )

        self.assertEqual(user.email, "alex.chen@refinery.internal")
        self.assertEqual(user.password_hash, "hashed_pw_999")
        self.assertTrue(user.is_active)
        self.assertTrue(len(user.user_id) > 0)
        self.assertEqual(mock_cursor.execute.call_count, 5)  # 3 in _ensure_tables + 2 inserts
        mock_conn.commit.assert_called()

    @patch.object(UserRepository, "_connect")
    def test_get_user_by_id(self, mock_connect: MagicMock) -> None:
        """Verify get_user_by_id parses database row into User dataclass."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "user_id": "usr-123",
            "email": "engineer@plant.internal",
            "password_hash": "hash_abc",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        user = self.repo.get_user_by_id("usr-123")
        self.assertIsNotNone(user)
        self.assertEqual(user.user_id, "usr-123")
        self.assertEqual(user.email, "engineer@plant.internal")

    @patch.object(UserRepository, "_connect")
    def test_get_profile_parses_jsonb_skills(self, mock_connect: MagicMock) -> None:
        """Verify get_profile parses JSONB array of skills into list of strings."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "user_id": "usr-456",
            "name": "Dr. Marcus Vance",
            "skill_set": '["Process engineering", "Refinery operations", "Equipment troubleshooting"]',
            "designation": "Senior Process Engineer",
            "refinery_experience_level": "expert",
            "preferred_explanation_depth": "concise",
            "created_at": now,
            "updated_at": now,
        }
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        profile = self.repo.get_profile("usr-456")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.user_id, "usr-456")
        self.assertEqual(profile.refinery_experience_level, "expert")
        self.assertEqual(profile.preferred_explanation_depth, "concise")
        self.assertEqual(
            profile.skill_set,
            ["Process engineering", "Refinery operations", "Equipment troubleshooting"],
        )

    @patch.object(UserRepository, "_connect")
    def test_update_profile_validation_and_execution(self, mock_connect: MagicMock) -> None:
        """Verify update_profile validates values and updates fields."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # First call gets current profile, second call returns updated profile
        current_row = {
            "user_id": "usr-789",
            "name": "Jane Doe",
            "skill_set": ["General"],
            "designation": "Operator",
            "refinery_experience_level": "intermediate",
            "preferred_explanation_depth": "moderate",
            "created_at": now,
            "updated_at": now,
        }
        updated_row = dict(current_row, designation="Shift Lead", refinery_experience_level="advanced")
        mock_cursor.fetchone.side_effect = [current_row, updated_row]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        updated = self.repo.update_profile(
            user_id="usr-789",
            designation="Shift Lead",
            refinery_experience_level="advanced",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.designation, "Shift Lead")
        self.assertEqual(updated.refinery_experience_level, "advanced")

    @patch.object(UserRepository, "_connect")
    def test_delete_user(self, mock_connect: MagicMock) -> None:
        """Verify delete_user executes DELETE statement."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        deleted = self.repo.delete_user("usr-delete-me")
        self.assertTrue(deleted)


if __name__ == "__main__":
    unittest.main()
