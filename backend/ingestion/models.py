"""Domain models used across the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ingestion.vision_models import VisualEvidence


@dataclass(frozen=True)
class DocumentContent:
    """Represents parsed document content for ingestion stages."""

    filename: str
    text: str
    pages: tuple[str, ...]
    page_count: int
    metadata: dict[str, str | int | bool | float]
    visual_evidence: tuple[VisualEvidence, ...] = ()
