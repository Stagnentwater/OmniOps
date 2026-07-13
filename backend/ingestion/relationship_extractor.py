"""Relationship Extraction service for the ingestion pipeline."""

from __future__ import annotations
import hashlib
import re
from typing import Any

from ingestion.chunk_models import Chunk, ChunkCollection
from ingestion.entity_models import EntityOccurrence, EntityOccurrenceCollection
from ingestion.relationship_models import RelationshipOccurrence, RelationshipOccurrenceCollection


def _get_context_window(
    chunk_text: str,
    text_a: str,
    text_b: str,
    idx_a: int,
    idx_b: int,
    window: int = 50
) -> str:
    """Extract context substring around both entities, including connecting text."""
    start_idx = max(0, min(idx_a, idx_b) - window)
    end_idx = min(len(chunk_text), max(idx_a + len(text_a), idx_b + len(text_b)) + window)
    return chunk_text[start_idx:end_idx].lower()


def _scan_context(context_text: str, keywords: list[str]) -> bool:
    """Check if any relational keyword matches in context."""
    for kw in keywords:
        pattern = rf'\b{re.escape(kw)}\b'
        if re.search(pattern, context_text):
            return True
    return False


def extract_relationships(
    entity_collection: EntityOccurrenceCollection,
    chunk_collection: ChunkCollection
) -> RelationshipOccurrenceCollection:
    """Identify and extract relationship occurrences from EntityOccurrenceCollection.

    Scans eligible pairs of entity occurrences in the same chunk for relational patterns.
    Directional rules are applied deterministically based on relationship type definitions.
    """
    document_id = entity_collection.document_id
    relationships_list: list[RelationshipOccurrence] = []

    # Map chunk IDs to their Chunk objects
    chunk_map: dict[str, Chunk] = {c.chunk_id: c for c in chunk_collection.chunks}

    # Group occurrences by chunk_id
    chunk_occurrences: dict[str, list[EntityOccurrence]] = {}
    for occ in entity_collection.occurrences:
        chunk_occurrences.setdefault(occ.chunk_id, []).append(occ)

    # Keyword lists for the 8 relationship types (REL-001 to REL-008)
    rel_keywords = {
        "HAS_COMPONENT": ["has", "contains", "equipped", "consists", "features", "with", "includes", "integrated", "comprises", "mount"],
        "CONNECTED_TO": ["connected", "linked", "couples", "piped", "leads", "flows", "coupled", "joins", "attach", "wiring"],
        "MAINTAINED_BY": ["maintained", "serviced", "repaired", "overhauled", "work by", "assigned", "fix", "maintenance", "repair"],
        "LOCATED_IN": ["located", "in", "at", "positioned", "installed", "situated", "inside", "placed"],
        "INSPECTED_BY": ["inspected", "checked", "audited", "verified", "examined", "inspection"],
        "CAUSES": ["causes", "leads", "resulting", "triggers", "due to", "source", "induces", "resulted", "origin"],
        "REFERENCES": ["references", "complies", "according", "per", "under", "standard", "governed", "ref"],
        "SIMILAR_TO": ["similar", "like", "analogous", "equivalent", "same as", "resembles", "identical"]
    }

    for chunk_id, occurrences in chunk_occurrences.items():
        if chunk_id not in chunk_map:
            continue
        chunk_text = chunk_map[chunk_id].text
        page_index = chunk_map[chunk_id].page_index

        occ_count = len(occurrences)
        # Scan all pairs of occurrences in this chunk
        for i in range(occ_count):
            for j in range(i + 1, occ_count):
                occ_a = occurrences[i]
                occ_b = occurrences[j]

                text_a = occ_a.original_text
                text_b = occ_b.original_text

                # Find positions in chunk text
                idx_a = chunk_text.find(text_a)
                idx_b = chunk_text.find(text_b)

                # Skip if not found
                if idx_a == -1 or idx_b == -1:
                    continue

                context_text = _get_context_window(chunk_text, text_a, text_b, idx_a, idx_b)

                # Set of candidate relationships to check
                candidates: list[tuple[str, EntityOccurrence, EntityOccurrence]] = []

                # Helper to add candidate based on type matches
                def check_and_add(
                    rel_type: str,
                    source_types: list[str],
                    target_types: list[str],
                    exact_type_match: bool = False
                ) -> None:
                    # Direction 1: A -> B
                    if occ_a.entity_type in source_types and occ_b.entity_type in target_types:
                        if not exact_type_match or occ_a.entity_type == occ_b.entity_type:
                            if occ_a.entity_type == occ_b.entity_type:
                                if idx_a < idx_b:
                                    candidates.append((rel_type, occ_a, occ_b))
                            else:
                                candidates.append((rel_type, occ_a, occ_b))

                    # Direction 2: B -> A
                    if occ_b.entity_type in source_types and occ_a.entity_type in target_types:
                        if not exact_type_match or occ_a.entity_type == occ_b.entity_type:
                            if occ_a.entity_type == occ_b.entity_type:
                                if idx_b < idx_a:
                                    candidates.append((rel_type, occ_b, occ_a))
                            else:
                                candidates.append((rel_type, occ_b, occ_a))

                # REL-001: HAS_COMPONENT (asset -> component)
                check_and_add("HAS_COMPONENT", ["asset"], ["component"])

                # REL-002: CONNECTED_TO (asset -> asset)
                if occ_a.entity_id != occ_b.entity_id:
                    check_and_add("CONNECTED_TO", ["asset"], ["asset"])

                # REL-003: MAINTAINED_BY (asset/component -> person)
                check_and_add("MAINTAINED_BY", ["asset", "component"], ["person"])

                # REL-004: LOCATED_IN (asset/component/person/event -> location)
                check_and_add("LOCATED_IN", ["asset", "component", "person", "event"], ["location"])

                # REL-005: INSPECTED_BY (asset/component -> person)
                check_and_add("INSPECTED_BY", ["asset", "component"], ["person"])

                # REL-006: CAUSES (component/parameter/failure_type -> failure_type/event)
                check_and_add("CAUSES", ["component", "parameter", "failure_type"], ["failure_type", "event"])

                # REL-007: REFERENCES (asset/component/person/event -> regulation/date)
                check_and_add("REFERENCES", ["asset", "component", "person", "event"], ["regulation", "date"])

                # REL-008: SIMILAR_TO (same types)
                if occ_a.entity_id != occ_b.entity_id:
                    check_and_add("SIMILAR_TO", ["asset", "component", "failure_type"], ["asset", "component", "failure_type"], exact_type_match=True)

                # Process candidates
                for rel_type, src, tgt in candidates:
                    keywords = rel_keywords.get(rel_type, [])
                    if _scan_context(context_text, keywords):
                        # Determine confidence: direct contextual match yields 0.95
                        confidence = 0.95

                        # Generate deterministic ID
                        raw_id = f"{document_id}_{chunk_id}_{rel_type}_{src.entity_id}_{tgt.entity_id}"
                        relationship_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

                        relationships_list.append(RelationshipOccurrence(
                            relationship_id=relationship_id,
                            relationship_type=rel_type,
                            source_occurrence_id=src.entity_id,
                            target_occurrence_id=tgt.entity_id,
                            source_canonical_name=src.canonical_name,
                            target_canonical_name=tgt.canonical_name,
                            confidence=confidence,
                            chunk_id=chunk_id,
                            document_id=document_id,
                            page_index=page_index,
                            metadata={}
                        ))

    # De-duplicate identical relationship occurrences in the same chunk
    unique_rels: dict[tuple[str, str, str, str], RelationshipOccurrence] = {}
    for rel in relationships_list:
        key = (rel.chunk_id, rel.relationship_type, rel.source_occurrence_id, rel.target_occurrence_id)
        if key in unique_rels:
            if rel.confidence <= unique_rels[key].confidence:
                continue
        unique_rels[key] = rel

    final_relationships = tuple(unique_rels.values())
    return RelationshipOccurrenceCollection(
        document_id=document_id,
        relationships=final_relationships,
        relationship_count=len(final_relationships)
    )
