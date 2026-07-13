"""Models representing relationship occurrences extracted from document chunks."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RelationshipOccurrence:
    """Represents an occurrence of a relationship between two entity occurrences in a chunk."""

    relationship_id: str         # Deterministic hash of document_id + chunk_id + relationship_type + source + target
    relationship_type: str       # HAS_COMPONENT, CONNECTED_TO, MAINTAINED_BY, LOCATED_IN, INSPECTED_BY, CAUSES, REFERENCES, SIMILAR_TO
    source_occurrence_id: str    # entity_id of the source occurrence
    target_occurrence_id: str    # entity_id of the target occurrence
    source_canonical_name: str   # Cleaned source name for verification
    target_canonical_name: str   # Cleaned target name for verification
    confidence: float            # Confidence score (0.0 to 1.0)
    chunk_id: str                # Originating chunk reference
    document_id: str             # Originating document reference
    page_index: int              # Page reference
    metadata: dict[str, str | int | bool | float]


@dataclass(frozen=True)
class RelationshipOccurrenceCollection:
    """Immutable collection of relationship occurrences for a single document."""

    document_id: str
    relationships: tuple[RelationshipOccurrence, ...]
    relationship_count: int
