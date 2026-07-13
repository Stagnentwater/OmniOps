"""Models representing entity occurrences extracted from document chunks."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntityOccurrence:
    """Represents an extracted entity occurrence from a specific document chunk."""

    entity_id: str       # Hash of document_id + chunk_id + entity_type + original_text
    entity_type: str     # asset, component, person, location, date, parameter, failure_type, regulation, event
    canonical_name: str  # Cleaned/normalized local name (e.g., "Pump P301")
    original_text: str   # Raw matched text from the chunk
    confidence: float    # Confidence score from 0.0 to 1.0
    chunk_id: str        # Originating chunk reference
    document_id: str     # Originating document reference
    page_index: int      # Physical page reference
    metadata: dict[str, str | int | bool | float]  # Type-specific attributes


@dataclass(frozen=True)
class EntityOccurrenceCollection:
    """Immutable collection of EntityOccurrence objects for a single document."""

    document_id: str
    occurrences: tuple[EntityOccurrence, ...]
    occurrence_count: int
    
