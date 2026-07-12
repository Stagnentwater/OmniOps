"""CSV parsing utilities for the ingestion pipeline."""

from __future__ import annotations

import csv
from io import BytesIO, TextIOWrapper
from typing import Any

from ingestion.models import DocumentContent


def _detect_encoding(csv_bytes: bytes) -> str:
    """Detect encoding of CSV bytes. Returns 'utf-8' or 'latin-1'."""
    try:
        csv_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        try:
            csv_bytes.decode("latin-1")
            return "latin-1"
        except UnicodeDecodeError:
            return "utf-8"


def _row_to_human_readable(headers: list[str], row: list[str]) -> str:
    """Convert a CSV row into human-readable key-value format."""
    pairs: list[str] = []
    for header, value in zip(headers, row):
        pairs.append(f"{header}: {value}")
    return "\n".join(pairs)


def parse_csv(*, csv_bytes: bytes, filename: str) -> DocumentContent:
    """Parse CSV bytes into a structured DocumentContent object.

    CSV files are converted into human-readable row representations for effective
    downstream embedding and entity extraction. Each row becomes a page element
    with key-value pairs rather than raw comma-separated values.
    """
    if not csv_bytes:
        raise ValueError("csv_bytes must not be empty")
    if not filename:
        raise ValueError("filename must not be empty")

    encoding = _detect_encoding(csv_bytes)

    try:
        text_wrapper = TextIOWrapper(BytesIO(csv_bytes), encoding=encoding)
        reader = csv.reader(text_wrapper)
        rows = list(reader)
    except Exception as exc:
        raise ValueError("Unable to parse CSV bytes") from exc

    if not rows:
        raise ValueError("CSV contains no rows")

    headers = rows[0]
    if not headers:
        raise ValueError("CSV contains no columns")

    data_rows = rows[1:]
    readable_pages: list[str] = []

    for row in data_rows:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        readable_text = _row_to_human_readable(headers, row)
        readable_pages.append(readable_text)

    text = "\n\n".join(readable_pages)
    metadata: dict[str, str | int | bool] = {
        "column_names": ", ".join(headers),
        "row_count": len(data_rows),
        "column_count": len(headers),
        "delimiter": ",",
        "encoding": encoding,
    }

    return DocumentContent(
        filename=filename,
        text=text,
        pages=tuple(readable_pages),
        page_count=len(readable_pages),
        metadata=metadata,
    )
