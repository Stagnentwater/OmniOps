"""PostgreSQL repositories for upload metadata and ingestion job records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

import psycopg

from config.settings import get_settings
from storage.models import StoredObject


@dataclass(frozen=True)
class DocumentMetadata:
    """Document metadata persisted after physical storage."""

    document_id: str
    file_name: str
    content_type: str
    stored_object: StoredObject


@dataclass(frozen=True)
class IngestionJobRecord:
    """Query view of an ingestion job lifecycle state."""

    job_id: str
    document_id: str
    status: str
    rq_job_id: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class MetadataRepository:
    """Persistence operations for documents and ingestion jobs."""

    def _connect(self) -> psycopg.Connection:
        settings = get_settings()
        return psycopg.connect(settings.postgres.dsn)

    def _ensure_tables(self, connection: psycopg.Connection) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    storage_key TEXT NOT NULL,
                    storage_backend TEXT NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    checksum TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rq_job_id TEXT,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (document_id)
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_job_events (
                    id BIGSERIAL PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
        connection.commit()

    def save_document_metadata(self, metadata: DocumentMetadata) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO documents (
                        document_id, file_name, content_type, storage_key, storage_backend,
                        size_bytes, checksum, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE
                    SET file_name = EXCLUDED.file_name,
                        content_type = EXCLUDED.content_type,
                        storage_key = EXCLUDED.storage_key,
                        storage_backend = EXCLUDED.storage_backend,
                        size_bytes = EXCLUDED.size_bytes,
                        checksum = EXCLUDED.checksum,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    (
                        metadata.document_id,
                        metadata.file_name,
                        metadata.content_type,
                        metadata.stored_object.storage_key,
                        metadata.stored_object.backend,
                        metadata.stored_object.size_bytes,
                        metadata.stored_object.checksum,
                        now,
                        now,
                    ),
                )
            connection.commit()

    def create_ingestion_job(self, *, document_id: str) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ingestion_jobs (job_id, document_id, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (job_id, document_id, "PENDING", now, now),
                )
                cursor.execute(
                    """
                    INSERT INTO ingestion_job_events (job_id, status, error, created_at)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (job_id, "PENDING", None, now),
                )
            connection.commit()
        return job_id

    def mark_job_enqueued(self, *, job_id: str, rq_job_id: str) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ingestion_jobs
                    SET rq_job_id = %s, updated_at = %s
                    WHERE job_id = %s;
                    """,
                    (rq_job_id, now, job_id),
                )
            connection.commit()

    def mark_job_queue_failed(self, *, job_id: str, error: str) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ingestion_jobs
                    SET status = %s, error = %s, updated_at = %s
                    WHERE job_id = %s;
                    """,
                    ("FAILED", error, now, job_id),
                )
                cursor.execute(
                    """
                    INSERT INTO ingestion_job_events (job_id, status, error, created_at)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (job_id, "FAILED", error, now),
                )
            connection.commit()

    def update_job_status(self, *, job_id: str, status: str, error: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ingestion_jobs
                    SET status = %s, error = %s, updated_at = %s
                    WHERE job_id = %s;
                    """,
                    (status, error, now, job_id),
                )
                cursor.execute(
                    """
                    INSERT INTO ingestion_job_events (job_id, status, error, created_at)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (job_id, status, error, now),
                )
            connection.commit()

    def get_ingestion_job(self, *, job_id: str) -> IngestionJobRecord | None:
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT job_id, document_id, status, rq_job_id, error, created_at, updated_at
                    FROM ingestion_jobs
                    WHERE job_id = %s;
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            return None
        return IngestionJobRecord(
            job_id=row[0],
            document_id=row[1],
            status=row[2],
            rq_job_id=row[3],
            error=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

    def list_job_events(self, *, job_id: str) -> list[dict[str, str | None]]:
        with self._connect() as connection:
            self._ensure_tables(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, error, created_at
                    FROM ingestion_job_events
                    WHERE job_id = %s
                    ORDER BY created_at ASC, id ASC;
                    """,
                    (job_id,),
                )
                rows = cursor.fetchall()
            connection.commit()
        return [
            {
                "status": status,
                "error": error,
                "created_at": created_at.isoformat(),
            }
            for status, error, created_at in rows
        ]
