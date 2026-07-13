"""Unit tests for Entity Extraction service in ingestion/extractor.py."""

import unittest

from ingestion.chunk_models import Chunk, ChunkCollection
from ingestion.entity_models import EntityOccurrence, EntityOccurrenceCollection
from ingestion.extractor import extract_entities


class TestEntityExtractor(unittest.TestCase):
    def test_extract_assets_ent_001(self):
        chunks = (
            Chunk(
                chunk_id="chk-1",
                document_id="doc-123",
                chunk_index=0,
                text="The Pump P-301 is active. Also check boiler B2.",
                page_index=0,
                section="System",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)

        self.assertIsInstance(results, EntityOccurrenceCollection)
        self.assertEqual(results.document_id, "doc-123")
        
        assets = [o for o in results.occurrences if o.entity_type == "asset"]
        self.assertEqual(len(assets), 2)
        
        canonical_names = {a.canonical_name for a in assets}
        self.assertIn("Pump P-301", canonical_names)
        self.assertIn("Boiler B2", canonical_names)

    def test_extract_components_ent_002(self):
        chunks = (
            Chunk(
                chunk_id="chk-2",
                document_id="doc-123",
                chunk_index=0,
                text="Replace the bearings and seals weekly.",
                page_index=0,
                section="System",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        components = [o for o in results.occurrences if o.entity_type == "component"]
        self.assertEqual(len(components), 2)
        
        canonical_names = {c.canonical_name for c in components}
        self.assertIn("Bearing", canonical_names)
        self.assertIn("Seal", canonical_names)

    def test_extract_people_ent_003(self):
        chunks = (
            Chunk(
                chunk_id="chk-3",
                document_id="doc-123",
                chunk_index=0,
                text="Engineer Smith checked the status with the Control Room Operator.",
                page_index=0,
                section="Staff",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        people = [o for o in results.occurrences if o.entity_type == "person"]
        self.assertEqual(len(people), 2)
        
        canonical_names = {p.canonical_name for p in people}
        self.assertIn("Engineer Smith", canonical_names)
        self.assertIn("Control Room Operator", canonical_names)

    def test_extract_locations_ent_004(self):
        chunks = (
            Chunk(
                chunk_id="chk-4",
                document_id="doc-123",
                chunk_index=0,
                text="Located in Area 1 and Plant A-12.",
                page_index=1,
                section="Details",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        locations = [o for o in results.occurrences if o.entity_type == "location"]
        self.assertEqual(len(locations), 2)
        
        canonical_names = {l.canonical_name for l in locations}
        self.assertIn("Area 1", canonical_names)
        self.assertIn("Plant A-12", canonical_names)

    def test_extract_dates_ent_005(self):
        chunks = (
            Chunk(
                chunk_id="chk-5",
                document_id="doc-123",
                chunk_index=0,
                text="The report dated 2026-07-12 was filed on 15/08/2026.",
                page_index=2,
                section="Details",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        dates = [o for o in results.occurrences if o.entity_type == "date"]
        self.assertEqual(len(dates), 2)
        
        canonical_names = {d.canonical_name for d in dates}
        self.assertIn("2026-07-12", canonical_names)
        self.assertIn("15/08/2026", canonical_names)

    def test_extract_parameters_ent_006(self):
        chunks = (
            Chunk(
                chunk_id="chk-6",
                document_id="doc-123",
                chunk_index=0,
                text="Verify the pressure weekly. Ensure it remains below 12.5 bar and vibration is under 2.4 mm/s.",
                page_index=0,
                section="Parameters",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        parameters = [o for o in results.occurrences if o.entity_type == "parameter"]
        self.assertEqual(len(parameters), 3)
        
        canonical_names = {p.canonical_name for p in parameters}
        self.assertIn("weekly", canonical_names)
        self.assertIn("12.5 bar", canonical_names)
        self.assertIn("2.4 mm/s", canonical_names)

    def test_extract_failures_ent_007(self):
        chunks = (
            Chunk(
                chunk_id="chk-7",
                document_id="doc-123",
                chunk_index=0,
                text="Warning for cavitation and overheating leaks.",
                page_index=0,
                section="Alerts",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        failures = [o for o in results.occurrences if o.entity_type == "failure_type"]
        self.assertEqual(len(failures), 3)
        
        canonical_names = {f.canonical_name for f in failures}
        self.assertIn("Cavitation", canonical_names)
        self.assertIn("Overheating", canonical_names)
        self.assertIn("Leak", canonical_names)

    def test_extract_regulations_ent_008(self):
        chunks = (
            Chunk(
                chunk_id="chk-8",
                document_id="doc-123",
                chunk_index=0,
                text="Complies with OSHA and ISO 9001-2015 regulations.",
                page_index=0,
                section="Safety",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        regs = [o for o in results.occurrences if o.entity_type == "regulation"]
        self.assertEqual(len(regs), 2)
        
        canonical_names = {r.canonical_name for r in regs}
        self.assertIn("OSHA", canonical_names)
        self.assertIn("ISO 9001-2015", canonical_names)

    def test_extract_events_ent_009(self):
        chunks = (
            Chunk(
                chunk_id="chk-9",
                document_id="doc-123",
                chunk_index=0,
                text="A Shutdown occurred. Followed by Repair under WO-456.",
                page_index=0,
                section="Events",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        events = [o for o in results.occurrences if o.entity_type == "event"]
        self.assertEqual(len(events), 3)
        
        canonical_names = {e.canonical_name for e in events}
        self.assertIn("Shutdown", canonical_names)
        self.assertIn("Repair", canonical_names)
        self.assertIn("Work Order WO-456", canonical_names)

    def test_duplicate_de_duplication_in_same_chunk(self):
        chunks = (
            Chunk(
                chunk_id="chk-10",
                document_id="doc-123",
                chunk_index=0,
                text="The bearing was checked. The bearing is functional.",
                page_index=0,
                section="Verification",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        components = [o for o in results.occurrences if o.entity_type == "component"]
        # Should be only 1 occurrence of "Bearing" due to de-duplication inside the chunk
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].canonical_name, "Bearing")

    def test_lineage_and_deterministic_ids(self):
        chunks = (
            Chunk(
                chunk_id="chk-11",
                document_id="doc-123",
                chunk_index=0,
                text="Pump P-301 was inspected during Maintenance.",
                page_index=4,
                section="Inspection",
                metadata={},
            ),
        )
        collection = ChunkCollection(document_id="doc-123", chunks=chunks, chunk_count=1)
        results = extract_entities(collection)
        
        self.assertEqual(results.occurrence_count, 2)  # Pump P-301 (asset), Maintenance (event)
        occurrence = [o for o in results.occurrences if o.entity_type == "asset"][0]
        
        # Verify lineage fields match source chunk
        self.assertEqual(occurrence.chunk_id, "chk-11")
        self.assertEqual(occurrence.document_id, "doc-123")
        self.assertEqual(occurrence.page_index, 4)
        
        # Verify deterministic ID
        raw_id = f"doc-123_chk-11_asset_{occurrence.original_text.strip()}"
        import hashlib
        expected_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
        self.assertEqual(occurrence.entity_id, expected_id)


if __name__ == "__main__":
    unittest.main()
