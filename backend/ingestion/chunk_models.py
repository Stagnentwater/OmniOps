"""Models representing chunks and collections of chunks for ingestion."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Chunk:
    """Represents a semantically cohesive chunk of document text."""

    chunk_id: str
    document_id: str
    chunk_index: int  # 0-indexed position within the document
    text: str
    page_index: int
    section: str | None
    metadata: dict[str, str | int | bool | float]


@dataclass(frozen=True)
class ChunkCollection:
    """Immutable collection of Chunk objects for a single document."""

    document_id: str
    chunks: tuple[Chunk, ...]
    chunk_count: int
