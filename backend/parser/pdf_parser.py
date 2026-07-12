"""PDF parsing utilities for the ingestion pipeline."""

from __future__ import annotations

from typing import Any

import fitz

from ingestion.models import DocumentContent


def _normalize_metadata(raw_metadata: dict[str, Any]) -> dict[str, str | int | bool]:
    normalized: dict[str, str | int | bool] = {}
    for key, value in raw_metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, bool, float)):
            normalized[key] = value
            continue
        normalized[key] = str(value)
    return normalized


def parse_pdf(*, pdf_bytes: bytes, filename: str) -> DocumentContent:
    """Parse native PDF bytes into a structured DocumentContent object."""
    if not pdf_bytes:
        raise ValueError("pdf_bytes must not be empty")
    if not filename:
        raise ValueError("filename must not be empty")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Unable to open PDF bytes") from exc

    try:
        if document.needs_pass:
            raise ValueError("Encrypted PDFs are not supported")

        page_texts: list[str] = []
        for page in document:
            page_texts.append(page.get_text())

        page_count = document.page_count
        text = "\n\n".join(page_texts)
        metadata = _normalize_metadata(document.metadata)

        return DocumentContent(
            filename=filename,
            text=text,
            pages=tuple(page_texts),
            page_count=page_count,
            metadata=metadata,
        )
    finally:
        document.close()
