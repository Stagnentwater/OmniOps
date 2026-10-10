"""Persistence operations for users and user profiles in PostgreSQL."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from config.settings import get_settings

logger = logging.getLogger(__name__)

VALID_EXPERIENCE_LEVELS = frozenset({"beginner", "intermediate", "advanced", "expert"})
VALID_EXPLANATION_DEPTHS = frozenset({"concise", "moderate", "detailed"})


@dataclass
class User:
    """Represents an authenticated user account."""

    user_id: str
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class UserProfile:
    """Represents domain expertise and explanation depth preferences for a user."""

    user_id: str
    name: str
    skill_set: list[str] = field(default_factory=list)
    designation: str = "Plant Personnel"
    refinery_experience_level: str = "intermediate"
    preferred_explanation_depth: str = "moderate"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class UserRepository:
    """Database repository for users and domain persona profiles."""

    def _connect(self) -> psycopg.Connection:
        settings = get_settings()
        return psycopg.connect(settings.postgres.dsn, row_factory=dict_row)

    def _ensure_tables(self, connection: psycopg.Connection) -> None:
        """Create users and user_profiles tables and indexes if they do not exist."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    skill_set JSONB NOT NULL DEFAULT '[]'::jsonb,
                    designation TEXT NOT NULL,
                    refinery_experience_level TEXT NOT NULL CHECK (
                        refinery_experience_level IN ('beginner', 'intermediate', 'advanced', 'expert')
                    ),
                    preferred_explanation_depth TEXT NOT NULL CHECK (
                        preferred_explanation_depth IN ('concise', 'moderate', 'detailed')
                    ),
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles (user_id);
                """
            )
            # Add user_id column to existing chat_sessions if not present
            cursor.execute(
                """
                ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users (user_id) ON DELETE CASCADE;
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions (user_id);
                """
            )
        connection.commit()

    def create_user(
        self,
        email: str,
        password_hash: str,
        name: str,
        designation: str = "Plant Personnel",
        skill_set: list[str] | None = None,
        refinery_experience_level: str = "intermediate",
        preferred_explanation_depth: str = "moderate",
    ) -> User:
        """Create a user identity and matching initial profile in a transaction."""
        clean_email = email.strip().lower()
        exp_level = refinery_experience_level.strip().lower()
        depth = preferred_explanation_depth.strip().lower()

        if exp_level not in VALID_EXPERIENCE_LEVELS:
            raise ValueError(
                f"Invalid experience level '{exp_level}'. Must be one of {sorted(VALID_EXPERIENCE_LEVELS)}"
            )
        if depth not in VALID_EXPLANATION_DEPTHS:
            raise ValueError(
                f"Invalid explanation depth '{depth}'. Must be one of {sorted(VALID_EXPLANATION_DEPTHS)}"
            )

        now = datetime.now(timezone.utc)
        user_id = str(uuid.uuid4())
        skills = list(skill_set) if skill_set is not None else []

        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (user_id, email, password_hash, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, clean_email, password_hash, True, now, now),
                )
                cursor.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id, name, skill_set, designation,
                        refinery_experience_level, preferred_explanation_depth,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        name.strip(),
                        json.dumps(skills),
                        designation.strip(),
                        exp_level,
                        depth,
                        now,
                        now,
                    ),
                )
            connection.commit()

        return User(
            user_id=user_id,
            email=clean_email,
            password_hash=password_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def get_user_by_id(self, user_id: str) -> User | None:
        """Fetch user by primary key."""
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, email, password_hash, is_active, created_at, updated_at
                    FROM users
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return User(**row)

    def get_user_by_email(self, email: str) -> User | None:
        """Fetch user by unique email address."""
        clean_email = email.strip().lower()
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, email, password_hash, is_active, created_at, updated_at
                    FROM users
                    WHERE email = %s
                    """,
                    (clean_email,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return User(**row)

    def get_profile(self, user_id: str) -> UserProfile | None:
        """Fetch domain persona profile by user_id."""
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, name, skill_set, designation,
                           refinery_experience_level, preferred_explanation_depth,
                           created_at, updated_at
                    FROM user_profiles
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                skills = row.get("skill_set", [])
                if isinstance(skills, str):
                    try:
                        skills = json.loads(skills)
                    except Exception:
                        skills = []
                elif not isinstance(skills, list):
                    skills = []

                return UserProfile(
                    user_id=row["user_id"],
                    name=row["name"],
                    skill_set=skills,
                    designation=row["designation"],
                    refinery_experience_level=row["refinery_experience_level"],
                    preferred_explanation_depth=row["preferred_explanation_depth"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

    def update_profile(
        self,
        user_id: str,
        name: str | None = None,
        designation: str | None = None,
        skill_set: list[str] | None = None,
        refinery_experience_level: str | None = None,
        preferred_explanation_depth: str | None = None,
    ) -> UserProfile | None:
        """Update profile fields for the given user_id."""
        now = datetime.now(timezone.utc)
        current = self.get_profile(user_id)
        if not current:
            return None

        new_name = name.strip() if name is not None else current.name
        new_desig = designation.strip() if designation is not None else current.designation
        new_skills = list(skill_set) if skill_set is not None else current.skill_set

        new_exp = (
            refinery_experience_level.strip().lower()
            if refinery_experience_level is not None
            else current.refinery_experience_level
        )
        if new_exp not in VALID_EXPERIENCE_LEVELS:
            raise ValueError(
                f"Invalid experience level '{new_exp}'. Must be one of {sorted(VALID_EXPERIENCE_LEVELS)}"
            )

        new_depth = (
            preferred_explanation_depth.strip().lower()
            if preferred_explanation_depth is not None
            else current.preferred_explanation_depth
        )
        if new_depth not in VALID_EXPLANATION_DEPTHS:
            raise ValueError(
                f"Invalid explanation depth '{new_depth}'. Must be one of {sorted(VALID_EXPLANATION_DEPTHS)}"
            )

        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_profiles
                    SET name = %s,
                        designation = %s,
                        skill_set = %s,
                        refinery_experience_level = %s,
                        preferred_explanation_depth = %s,
                        updated_at = %s
                    WHERE user_id = %s
                    """,
                    (
                        new_name,
                        new_desig,
                        json.dumps(new_skills),
                        new_exp,
                        new_depth,
                        now,
                        user_id,
                    ),
                )
            connection.commit()

        return self.get_profile(user_id)

    def delete_user(self, user_id: str) -> bool:
        """Delete user account (cascades to profile and sessions)."""
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                deleted = cursor.rowcount > 0
            connection.commit()
        return deleted
