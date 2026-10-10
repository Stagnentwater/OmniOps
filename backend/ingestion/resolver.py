"""Knowledge Resolution service for resolving raw occurrences into canonical entities/relationships."""

from __future__ import annotations
import hashlib
import re
from typing import Any

from ingestion.entity_models import EntityOccurrence, EntityOccurrenceCollection
from ingestion.relationship_models import RelationshipOccurrence, RelationshipOccurrenceCollection
from ingestion.resolution_models import ResolvedEntity, ResolvedRelationship, ResolvedKnowledgePackage


from utils.tag_patterns import validate_and_parse_tag

def _normalize_entity_name(name: str, entity_type: str) -> str:
    """Normalize names of entity occurrences to establish standard keys for alias matching."""
    if entity_type == "asset":
        parsed = validate_and_parse_tag(name)
        if parsed:
            tag, _, _ = parsed
            return tag.lower().replace("-", "")
            
    cleaned = re.sub(r"\s+", " ", name).strip().lower()
    cleaned = cleaned.replace("-", "")
    return cleaned


def _calculate_noisy_or(confidences: list[float]) -> float:
    """Calculate aggregated confidence using the Noisy-OR formula."""
    prod = 1.0
    for conf in confidences:
        prod *= (1.0 - conf)
    return round(min(1.0, 1.0 - prod), 4)


def resolve_knowledge(
    entity_collection: EntityOccurrenceCollection,
    relationship_collection: RelationshipOccurrenceCollection
) -> ResolvedKnowledgePackage:
    """Perform alias resolution, property conflict resolution, and deterministic ID assignment.

    Consolidates raw entity/relationship occurrences into canonical ResolvedEntity/ResolvedRelationship objects.
    """
    document_id = entity_collection.document_id
    
    # 1. Group Entity Occurrences by type and normalized name
    grouped_occurrences: dict[tuple[str, str], list[EntityOccurrence]] = {}
    for occ in entity_collection.occurrences:
        norm_key = (occ.entity_type, _normalize_entity_name(occ.canonical_name, occ.entity_type))
        grouped_occurrences.setdefault(norm_key, []).append(occ)

    resolved_entities_list: list[ResolvedEntity] = []
    occurrence_to_canonical: dict[str, str] = {}

    for (ent_type, norm_key), occurrences in grouped_occurrences.items():
        # Select best canonical name (shortest string, to prefer bare tags like P-301 over Pump P-301)
        best_name = occurrences[0].canonical_name
        best_len = len(best_name)
        
        for occ in occurrences:
            name = occ.canonical_name
            name_len = len(name)
            
            if name_len < best_len:
                best_name = name
                best_len = name_len

        # Generate deterministic global canonical ID
        name_normalized = best_name.lower().replace(" ", "_")
        raw_id = f"{ent_type.lower()}_{name_normalized}"
        entity_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

        # Group and map occurrences to the resolved canonical ID
        occurrence_ids: list[str] = []
        confidences: list[float] = []
        properties_sources: list[tuple[float, dict[str, Any]]] = []

        for occ in occurrences:
            occurrence_to_canonical[occ.entity_id] = entity_id
            occurrence_ids.append(occ.entity_id)
            confidences.append(occ.confidence)
            properties_sources.append((occ.confidence, occ.metadata))

        # Calculate aggregated confidence using Noisy-OR
        resolved_confidence = _calculate_noisy_or(confidences)

        # Resolve property conflicts (value from occurrence with highest confidence wins)
        # Sort properties by confidence descending so highest confidence overrides
        properties_sources.sort(key=lambda x: x[0])
        resolved_properties: dict[str, str | int | bool | float] = {}
        for _, props in properties_sources:
            if props:
                resolved_properties.update(props)

        resolved_entities_list.append(ResolvedEntity(
            entity_id=entity_id,
            entity_type=ent_type,
            canonical_name=best_name,
            confidence=resolved_confidence,
            properties=resolved_properties,
            occurrences=tuple(occurrence_ids)
        ))

    # 2. Group Relationship Occurrences
    grouped_rels: dict[tuple[str, str, str], list[RelationshipOccurrence]] = {}
    for rel in relationship_collection.relationships:
        src_id = occurrence_to_canonical.get(rel.source_occurrence_id)
        tgt_id = occurrence_to_canonical.get(rel.target_occurrence_id)
        
        # Only process relationships if both source and target entities resolved successfully
        if src_id and tgt_id:
            rel_key = (rel.relationship_type, src_id, tgt_id)
            grouped_rels.setdefault(rel_key, []).append(rel)

    resolved_relationships_list: list[ResolvedRelationship] = []

    for (rel_type, src_id, tgt_id), rel_occurrences in grouped_rels.items():
        # Generate deterministic global relationship ID
        raw_id = f"{rel_type.lower()}_{src_id}_{tgt_id}"
        relationship_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

        rel_occurrence_ids: list[str] = []
        rel_confidences: list[float] = []
        rel_metadata_sources: list[tuple[float, dict[str, Any]]] = []

        for rel_occ in rel_occurrences:
            rel_occurrence_ids.append(rel_occ.relationship_id)
            rel_confidences.append(rel_occ.confidence)
            rel_metadata_sources.append((rel_occ.confidence, rel_occ.metadata))

        resolved_rel_confidence = _calculate_noisy_or(rel_confidences)

        # Resolve metadata conflicts using highest confidence source
        rel_metadata_sources.sort(key=lambda x: x[0])
        resolved_metadata: dict[str, str | int | bool | float] = {}
        for _, meta in rel_metadata_sources:
            if meta:
                resolved_metadata.update(meta)

        resolved_relationships_list.append(ResolvedRelationship(
            relationship_id=relationship_id,
            relationship_type=rel_type,
            source_entity_id=src_id,
            target_entity_id=tgt_id,
            confidence=resolved_rel_confidence,
            occurrences=tuple(rel_occurrence_ids),
            metadata=resolved_metadata
        ))

    return ResolvedKnowledgePackage(
        document_id=document_id,
        resolved_entities=tuple(resolved_entities_list),
        resolved_relationships=tuple(resolved_relationships_list),
        metadata={}
    )
