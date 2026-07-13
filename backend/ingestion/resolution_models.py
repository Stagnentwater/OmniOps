"""Models representing resolved entities and relationships for storage persistence."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedEntity:
    """Represents a globally resolved canonical entity with aggregated evidence."""

    entity_id: str         # Deterministic global canonical hash
    entity_type: str       # asset, component, person, location, etc.
    canonical_name: str    # Best candidate name (e.g. "Pump P-301" over "P-301")
    confidence: float      # Aggregated confidence score
    properties: dict[str, str | int | bool | float]  # Resolved attributes
    occurrences: tuple[str, ...]  # IDs of all originating EntityOccurrence objects


@dataclass(frozen=True)
class ResolvedRelationship:
    """Represents a resolved canonical relationship between two canonical entities."""

    relationship_id: str        # Deterministic global relationship hash
    relationship_type: str      # HAS_COMPONENT, CONNECTED_TO, etc.
    source_entity_id: str       # Canonical entity_id of source
    target_entity_id: str       # Canonical entity_id of target
    confidence: float           # Aggregated confidence score
    occurrences: tuple[str, ...]  # IDs of originating RelationshipOccurrence objects
    metadata: dict[str, str | int | bool | float]


@dataclass(frozen=True)
class ResolvedKnowledgePackage:
    """Consolidated resolved package ready for downstream storage."""

    document_id: str
    resolved_entities: tuple[ResolvedEntity, ...]
    resolved_relationships: tuple[ResolvedRelationship, ...]
    metadata: dict[str, str | int | bool | float]
