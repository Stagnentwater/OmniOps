"""Metadata extraction for ingested documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentMetadata:
    """Unified document metadata extracted and computed from parsed content."""

    # System fields (provided by pipeline, passed through)
    document_id: str
    filename: str
    upload_time: str
    storage_uri: str
    ingestion_job_id: str

    # File type (detected from extension)
    file_type: str

    # Document properties (extracted or computed)
    page_count: int
    word_count: int
    character_count: int
    title: str | None
    author: str | None
    language: str
    has_tables: bool
    has_images: bool
    reading_time_minutes: float
    file_hash: str
    parser_metadata: dict[str, str | int | bool]


def _detect_file_type(filename: str) -> str:
    """Detect file type from filename extension."""
    if not filename:
        return "unknown"

    extension = filename.lower().split(".")[-1] if "." in filename else ""
    supported = {"pdf", "docx", "csv"}
    return extension if extension in supported else "unknown"


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def _count_characters(text: str) -> int:
    """Count characters (excluding whitespace)."""
    return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))


def _estimate_reading_time(word_count: int, words_per_minute: int = 200) -> float:
    """Estimate reading time in minutes."""
    if word_count == 0:
        return 0.0
    return round(word_count / words_per_minute, 1)


def _compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def _detect_has_tables(
    parser_metadata: dict[str, str | int | bool],
) -> bool:
    """Detect presence of tables from parser metadata."""
    # CSV always has tables (rows)
    if parser_metadata.get("delimiter") == ",":
        return True
    # DOCX may report table presence
    if "table" in str(parser_metadata).lower():
        return True
    return False


def _detect_has_images(
    parser_metadata: dict[str, str | int | bool],
) -> bool:
    """Detect presence of images from parser metadata."""
    if "image" in str(parser_metadata).lower():
        return True
    return False


def extract_metadata(
    *,
    document_content,
    file_bytes: bytes,
    document_id: str,
    filename: str,
    upload_time: str,
    storage_uri: str,
    ingestion_job_id: str,
) -> DocumentMetadata:
    """Extract and compute unified document metadata.

    System fields (document_id, upload_time, storage_uri, ingestion_job_id)
    are provided by the pipeline and passed through unchanged.

    Document properties (page_count, word_count, etc.) are extracted or
    computed from the DocumentContent and file bytes.

    Document type classification (semantic understanding of content purpose)
    is deferred to a later stage and not performed here.
    """
    text = document_content.text
    parser_metadata = document_content.metadata or {}

    file_type = _detect_file_type(filename)
    word_count = _count_words(text)
    character_count = _count_characters(text)
    reading_time_minutes = _estimate_reading_time(word_count)
    file_hash = _compute_file_hash(file_bytes)

    title = parser_metadata.get("title")
    if isinstance(title, str) and title:
        title = title
    else:
        title = None

    author = parser_metadata.get("author")
    if isinstance(author, str) and author:
        author = author
    else:
        author = None

    has_tables = _detect_has_tables(parser_metadata)
    has_images = _detect_has_images(parser_metadata)

    return DocumentMetadata(
        document_id=document_id,
        filename=filename,
        upload_time=upload_time,
        storage_uri=storage_uri,
        ingestion_job_id=ingestion_job_id,
        file_type=file_type,
        page_count=document_content.page_count,
        word_count=word_count,
        character_count=character_count,
        title=title,
        author=author,
        language="unknown",
        has_tables=has_tables,
        has_images=has_images,
        reading_time_minutes=reading_time_minutes,
        file_hash=file_hash,
        parser_metadata=parser_metadata,
    )
