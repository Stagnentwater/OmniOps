"""Unit tests for Relationship Extraction service in ingestion/relationship_extractor.py."""

import unittest

from ingestion.chunk_models import Chunk, ChunkCollection
from ingestion.entity_models import EntityOccurrence, EntityOccurrenceCollection
from ingestion.relationship_models import RelationshipOccurrence, RelationshipOccurrenceCollection
from ingestion.relationship_extractor import extract_relationships


class TestRelationshipExtractor(unittest.TestCase):
    def setUp(self):
        self.doc_id = "doc-123"
        self.chunk_id = "chk-1"
        self.page_index = 0
        self.section = "System"

    def test_extract_has_component_rel_001(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="The Pump P-301 contains a mechanical seal.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-p301",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-seal",
            entity_type="component",
            canonical_name="Seal",
            original_text="mechanical seal",
            confidence=0.90,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "HAS_COMPONENT")
        self.assertEqual(rel.source_occurrence_id, "ent-p301")
        self.assertEqual(rel.target_occurrence_id, "ent-seal")

    def test_extract_connected_to_rel_002(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Pump P-301 is connected to Boiler B-2.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-p301",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-b2",
            entity_type="asset",
            canonical_name="Boiler B-2",
            original_text="Boiler B-2",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "CONNECTED_TO")
        self.assertEqual(rel.source_occurrence_id, "ent-p301")
        self.assertEqual(rel.target_occurrence_id, "ent-b2")

    def test_extract_maintained_by_rel_003(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Technician Smith repaired the Boiler B-2.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-tech",
            entity_type="person",
            canonical_name="Technician Smith",
            original_text="Technician Smith",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-b2",
            entity_type="asset",
            canonical_name="Boiler B-2",
            original_text="Boiler B-2",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "MAINTAINED_BY")
        self.assertEqual(rel.source_occurrence_id, "ent-b2")
        self.assertEqual(rel.target_occurrence_id, "ent-tech")

    def test_extract_located_in_rel_004(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Pump P-301 is located in Area 1.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-p301",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-area1",
            entity_type="location",
            canonical_name="Area 1",
            original_text="Area 1",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "LOCATED_IN")
        self.assertEqual(rel.source_occurrence_id, "ent-p301")
        self.assertEqual(rel.target_occurrence_id, "ent-area1")

    def test_extract_inspected_by_rel_005(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Inspected by Engineer Smith.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-p301",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-eng",
            entity_type="person",
            canonical_name="Engineer Smith",
            original_text="Engineer Smith",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        # Note: even if text has 'Inspected by Engineer Smith' but doesn't mention asset in this specific chunk line,
        # if the asset is also matched in this chunk (e.g. from context window), they'll connect.
        # Let's adjust chunk text to have both:
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Pump P-301 was inspected by Engineer Smith.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "INSPECTED_BY")
        self.assertEqual(rel.source_occurrence_id, "ent-p301")
        self.assertEqual(rel.target_occurrence_id, "ent-eng")

    def test_extract_causes_rel_006(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="High vibration triggers a Shutdown.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-vib",
            entity_type="failure_type",
            canonical_name="Vibration",
            original_text="vibration",
            confidence=0.90,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-shutdown",
            entity_type="event",
            canonical_name="Shutdown",
            original_text="Shutdown",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "CAUSES")
        self.assertEqual(rel.source_occurrence_id, "ent-vib")
        self.assertEqual(rel.target_occurrence_id, "ent-shutdown")

    def test_extract_references_rel_007(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Operation complies with OSHA guidelines.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-op",
            entity_type="event",
            canonical_name="Operation",
            original_text="Operation",
            confidence=0.90,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-osha",
            entity_type="regulation",
            canonical_name="OSHA",
            original_text="OSHA",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "REFERENCES")
        self.assertEqual(rel.source_occurrence_id, "ent-op")
        self.assertEqual(rel.target_occurrence_id, "ent-osha")

    def test_extract_similar_to_rel_008(self):
        chunk = Chunk(
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            chunk_index=0,
            text="Pump P-301 is similar to Pump P-302.",
            page_index=self.page_index,
            section=self.section,
            metadata={},
        )
        chunk_col = ChunkCollection(document_id=self.doc_id, chunks=(chunk,), chunk_count=1)

        occ_a = EntityOccurrence(
            entity_id="ent-p301",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        occ_b = EntityOccurrence(
            entity_id="ent-p302",
            entity_type="asset",
            canonical_name="Pump P-302",
            original_text="Pump P-302",
            confidence=0.95,
            chunk_id=self.chunk_id,
            document_id=self.doc_id,
            page_index=self.page_index,
            metadata={}
        )
        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )

        results = extract_relationships(entity_col, chunk_col)
        self.assertEqual(results.relationship_count, 1)
        rel = results.relationships[0]
        self.assertEqual(rel.relationship_type, "SIMILAR_TO")
        self.assertEqual(rel.source_occurrence_id, "ent-p301")
        self.assertEqual(rel.target_occurrence_id, "ent-p302")


if __name__ == "__main__":
    unittest.main()
