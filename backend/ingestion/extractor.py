"""Entity Extraction service for the ingestion pipeline."""

from __future__ import annotations
import hashlib
import re
from typing import Any

from ingestion.chunk_models import Chunk, ChunkCollection
from ingestion.entity_models import EntityOccurrence, EntityOccurrenceCollection


def _clean_text(text: str) -> str:
    """Normalize whitespace and clean up matched text."""
    return re.sub(r"\s+", " ", text).strip()


def extract_entities(chunk_collection: ChunkCollection) -> EntityOccurrenceCollection:
    """Extract entity occurrences from a collection of document chunks.

    Coordinates extraction across 9 categories (ENT-001 to ENT-009)
    using rule-based patterns and lookups. De-duplicates identical occurrences
    within each chunk by keeping the highest confidence match.
    """
    document_id = chunk_collection.document_id
    occurrences_list: list[EntityOccurrence] = []

    # Compile Regex Patterns for all 9 categories
    
    # ENT-001: Equipment (Assets)
    asset_pattern = re.compile(
        r'\b(Pump|Boiler|Valve|Compressor|Generator|Turbine|Motor|Fan|Chiller|Heater)\s*([A-Za-z0-9\-]+)\b',
        re.IGNORECASE
    )
    asset_tag_pattern = re.compile(r'\b(P|B|V|C|G|T|M|F|CH|H)-([0-9]{3,4})\b', re.IGNORECASE)

    # ENT-002: Components
    component_pattern = re.compile(
        r'\b(bearing|seal|impeller|gasket|coupling|shaft|valve\s+stem|o-ring|rotor|stator|gearbox|piston|cylinder)s?\b',
        re.IGNORECASE
    )

    # ENT-003: People (Roles & Names)
    people_pattern = re.compile(
        r'\b(Engineer|Inspector|Technician|Operator|Supervisor)\s+([A-Z][a-z]+)\b',
        re.IGNORECASE
    )
    people_role_pattern = re.compile(
        r'\b(Maintenance Technician|Lead Engineer|Control Room Operator|Safety Inspector)\b',
        re.IGNORECASE
    )

    # ENT-004: Locations
    location_pattern = re.compile(
        r'\b(Plant|Area|Line|Zone|Room|Bay|Section)\s+([A-Za-z0-9\-]+)\b',
        re.IGNORECASE
    )

    # ENT-005: Dates
    date_iso = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
    date_slash = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
    date_textual = re.compile(
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s+\d{4})?\b',
        re.IGNORECASE
    )

    # ENT-006: Parameters & Intervals
    interval_pattern = re.compile(r'\b(every\s+\d+\s+(?:hours|days|weeks|months|years|cycles))\b', re.IGNORECASE)
    interval_keyword = re.compile(r'\b(monthly|weekly|daily|annually)\b', re.IGNORECASE)
    param_pattern = re.compile(r'\b(\d+(?:\.\d+)?\s*(?:bar|psi|mm/s|RPM|gpm|°C|°F|C|F))\b', re.IGNORECASE)

    # ENT-007: Failure Types
    failure_pattern = re.compile(
        r'\b(vibration|overheating|leak|cavitation|fatigue|wear|alignment\s+error|corrosion|clogging|blockage|fault|trip|rupture)s?\b',
        re.IGNORECASE
    )

    # ENT-008: Regulations
    regulation_pattern = re.compile(
        r'\b(OSHA|ASME|EPA|ANSI|API\s+\d+|ISO\s+\d+(?:-\d+)?)\b',
        re.IGNORECASE
    )

    # ENT-009: Work Orders & Events
    wo_pattern = re.compile(r'\b(WO-?\d+|\bWork\s+Order\s+\d+)\b', re.IGNORECASE)
    event_pattern = re.compile(
        r'\b(Inspection|Maintenance|Shutdown|Repair|Replacement|Overhaul)\b',
        re.IGNORECASE
    )

    for chunk in chunk_collection.chunks:
        chunk_id = chunk.chunk_id
        page_index = chunk.page_index
        text = chunk.text
        
        # Dictionary to de-duplicate matches within this specific chunk
        # Key: (entity_type, normalized_matched_text)
        chunk_occurrences: dict[tuple[str, str], EntityOccurrence] = {}

        def add_occurrence(
            entity_type: str,
            original_text: str,
            canonical_name: str,
            confidence: float,
            properties: dict[str, str | int | bool | float] | None = None
        ) -> None:
            norm_text = canonical_name.lower().strip()
            key = (entity_type, norm_text)
            
            # Generate deterministic occurrence ID
            raw_id = f"{document_id}_{chunk_id}_{entity_type}_{original_text.strip()}"
            entity_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

            # Keep highest confidence match for this type/value in the chunk
            if key in chunk_occurrences:
                if confidence <= chunk_occurrences[key].confidence:
                    return

            chunk_occurrences[key] = EntityOccurrence(
                entity_id=entity_id,
                entity_type=entity_type,
                canonical_name=canonical_name,
                original_text=original_text,
                confidence=confidence,
                chunk_id=chunk_id,
                document_id=document_id,
                page_index=page_index,
                metadata=properties or {}
            )

        # 1. ENT-001 Assets
        # Check standard prefix matches (e.g. Pump P301)
        for match in asset_pattern.finditer(text):
            orig = match.group(0)
            asset_type = match.group(1).capitalize()
            tag = match.group(2).upper()
            canonical = f"{asset_type} {tag}"
            add_occurrence("asset", orig, canonical, 0.95, {"asset_type": asset_type, "tag": tag})

        # Check raw tag patterns (e.g. P-301)
        for match in asset_tag_pattern.finditer(text):
            orig = match.group(0)
            prefix = match.group(1).upper()
            num = match.group(2)
            
            # Resolve prefix to type
            prefix_to_type = {
                "P": "Pump", "B": "Boiler", "V": "Valve", "C": "Compressor",
                "G": "Generator", "T": "Turbine", "M": "Motor", "F": "Fan",
                "CH": "Chiller", "H": "Heater"
            }
            asset_type = prefix_to_type.get(prefix, "Equipment")
            canonical = f"{asset_type} {prefix}-{num}"
            add_occurrence("asset", orig, canonical, 0.85, {"asset_type": asset_type, "tag": f"{prefix}-{num}"})

        # 2. ENT-002 Components
        for match in component_pattern.finditer(text):
            orig = match.group(0)
            canonical = orig.lower().strip()
            # Standardize singular form if ending in 's'
            if canonical.endswith("s") and not canonical.endswith("ss"):
                canonical = canonical[:-1]
            add_occurrence("component", orig, canonical.capitalize(), 0.90)

        # 3. ENT-003 People
        for match in people_pattern.finditer(text):
            orig = match.group(0)
            role = match.group(1).capitalize()
            name = match.group(2)
            canonical = f"{role} {name}"
            add_occurrence("person", orig, canonical, 0.95, {"role": role, "name": name})

        for match in people_role_pattern.finditer(text):
            orig = match.group(0)
            canonical = orig.title().strip()
            add_occurrence("person", orig, canonical, 0.90, {"role": canonical})

        # 4. ENT-004 Locations
        for match in location_pattern.finditer(text):
            orig = match.group(0)
            loc_type = match.group(1).capitalize()
            loc_val = match.group(2)
            canonical = f"{loc_type} {loc_val}"
            add_occurrence("location", orig, canonical, 0.95, {"location_type": loc_type, "value": loc_val})

        # 5. ENT-005 Dates
        for match in date_iso.finditer(text):
            orig = match.group(0)
            add_occurrence("date", orig, orig, 0.95, {"format": "ISO"})
        for match in date_slash.finditer(text):
            orig = match.group(0)
            add_occurrence("date", orig, orig, 0.95, {"format": "slash"})
        for match in date_textual.finditer(text):
            orig = match.group(0)
            add_occurrence("date", orig, _clean_text(orig), 0.90, {"format": "textual"})

        # 6. ENT-006 Parameters & Intervals
        for match in interval_pattern.finditer(text):
            orig = match.group(0)
            add_occurrence("parameter", orig, orig.lower().strip(), 0.95, {"param_type": "interval"})
        for match in interval_keyword.finditer(text):
            orig = match.group(0)
            add_occurrence("parameter", orig, orig.lower().strip(), 0.90, {"param_type": "interval"})
        for match in param_pattern.finditer(text):
            orig = match.group(0)
            add_occurrence("parameter", orig, orig.strip(), 0.85, {"param_type": "measurement"})

        # 7. ENT-007 Failure Types
        for match in failure_pattern.finditer(text):
            orig = match.group(0)
            canonical = orig.lower().strip()
            if canonical.endswith("s") and not canonical.endswith("ss"):
                canonical = canonical[:-1]
            add_occurrence("failure_type", orig, canonical.capitalize(), 0.90)

        # 8. ENT-008 Regulations
        for match in regulation_pattern.finditer(text):
            orig = match.group(0)
            canonical = orig.upper().strip()
            add_occurrence("regulation", orig, canonical, 0.95)

        # 9. ENT-009 Work Orders & Events
        for match in wo_pattern.finditer(text):
            orig = match.group(0)
            tag = orig.upper().replace(" ", "")
            if not tag.startswith("WO"):
                tag = "WO-" + tag.replace("WORKORDER", "")
            canonical = f"Work Order {tag}"
            add_occurrence("event", orig, canonical, 0.95, {"event_type": "work_order", "tag": tag})

        for match in event_pattern.finditer(text):
            orig = match.group(0)
            canonical = orig.capitalize().strip()
            add_occurrence("event", orig, canonical, 0.85, {"event_type": "general_event"})

        # Collect occurrences from chunk
        occurrences_list.extend(chunk_occurrences.values())

    return EntityOccurrenceCollection(
        document_id=document_id,
        occurrences=tuple(occurrences_list),
        occurrence_count=len(occurrences_list)
    )
