"""Domain models used across the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentContent:
    """Represents parsed document content for ingestion stages."""

    filename: str
    text: str
    pages: tuple[str, ...]
    page_count: int
    metadata: dict[str, str | int | bool | float]
