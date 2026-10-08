"""PostgreSQL repository for chat sessions and messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any
import uuid

import psycopg
from psycopg.rows import dict_row

from config.settings import get_settings


@dataclass
class ChatSession:
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ChatMessage:
    message_id: str
    session_id: str
    role: str
    content: str
    citations: list[dict]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatRepository:
    """Persistence operations for chat history."""

    def _connect(self) -> psycopg.Connection:
        settings = get_settings()
        return psycopg.connect(settings.postgres.dsn, row_factory=dict_row)

    def _ensure_tables(self, connection: psycopg.Connection) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations JSONB,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id) ON DELETE CASCADE
                );
                ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS metadata JSONB;
                """
            )
        connection.commit()

    def create_session(self, title: str = "New Chat") -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session_id, title, now, now),
                )
            connection.commit()
        return session_id

    def list_sessions(self) -> list[ChatSession]:
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, title, created_at, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                    """
                )
                rows = cursor.fetchall()
                
        return [
            ChatSession(
                session_id=row["session_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Auto-update title if it's the first user message
        if role == "user":
            with self._connect() as connection:
                self._ensure_tables(connection)
                with connection.cursor() as cursor:
                    # Check if title is default
                    cursor.execute(
                        "SELECT title FROM chat_sessions WHERE session_id = %s",
                        (session_id,)
                    )
                    row = cursor.fetchone()
                    if row and row["title"] == "New Chat":
                        # Generate simple title from first few words
                        title = " ".join(content.split()[:5]) + ("..." if len(content.split()) > 5 else "")
                        cursor.execute(
                            "UPDATE chat_sessions SET title = %s, updated_at = %s WHERE session_id = %s",
                            (title, now, session_id)
                        )
                connection.commit()

        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_messages (message_id, session_id, role, content, citations, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        message_id,
                        session_id,
                        role,
                        content,
                        json.dumps(citations) if citations else None,
                        json.dumps(metadata) if metadata else None,
                        now,
                    ),
                )
                
                # Update session updated_at
                cursor.execute(
                    """
                    UPDATE chat_sessions
                    SET updated_at = %s
                    WHERE session_id = %s
                    """,
                    (now, session_id),
                )
            connection.commit()
            
        return message_id

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT message_id, session_id, role, content, citations, metadata, created_at
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                    """,
                    (session_id,)
                )
                rows = cursor.fetchall()
                
        return [
            ChatMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                citations=row["citations"] if row["citations"] else [],
                created_at=row["created_at"],
                metadata=row.get("metadata") or {},
            )
            for row in rows
        ]

    def get_recent_messages(
        self,
        session_id: str,
        limit: int,
        exclude_message_id: str | None = None,
    ) -> list[ChatMessage]:
        """Return a bounded, chronological window of messages for one session.

        ``exclude_message_id`` lets a caller omit the just-persisted user message,
        keeping the current question separate from historical conversation context.
        """
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        query = """
            SELECT message_id, session_id, role, content, citations, metadata, created_at
            FROM (
                SELECT message_id, session_id, role, content, citations, metadata, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC, message_id DESC
                LIMIT %s
            ) AS recent_messages
            ORDER BY created_at ASC, message_id ASC
        """
        parameters: list[object] = [session_id, limit]
        if exclude_message_id is not None:
            query = """
                SELECT message_id, session_id, role, content, citations, metadata, created_at
                FROM (
                    SELECT message_id, session_id, role, content, citations, metadata, created_at
                    FROM chat_messages
                    WHERE session_id = %s AND message_id <> %s
                    ORDER BY created_at DESC, message_id DESC
                    LIMIT %s
                ) AS recent_messages
                ORDER BY created_at ASC, message_id ASC
            """
            parameters = [session_id, exclude_message_id, limit]

        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    parameters,
                )
                rows = cursor.fetchall()

        return [
            ChatMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                citations=row["citations"] if row["citations"] else [],
                created_at=row["created_at"],
                metadata=row.get("metadata") or {},
            )
            for row in rows
        ]

    def delete_session(self, session_id: str) -> None:
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM chat_sessions WHERE session_id = %s",
                    (session_id,)
                )
            connection.commit()
