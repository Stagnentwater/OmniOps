"""Unit tests for Knowledge Resolution service in ingestion/resolver.py."""

import unittest

from ingestion.entity_models import EntityOccurrence, EntityOccurrenceCollection
from ingestion.relationship_models import RelationshipOccurrence, RelationshipOccurrenceCollection
from ingestion.resolution_models import ResolvedKnowledgePackage
from ingestion.resolver import resolve_knowledge, _normalize_entity_name, _calculate_noisy_or


class TestKnowledgeResolver(unittest.TestCase):
    def setUp(self):
        self.doc_id = "doc-123"

    def test_normalize_entity_name_heuristics(self):
        self.assertEqual(_normalize_entity_name("Pump P-301", "asset"), "pump p301")
        self.assertEqual(_normalize_entity_name("p-301", "asset"), "pump p301")
        self.assertEqual(_normalize_entity_name("P301", "asset"), "pump p301")
        self.assertEqual(_normalize_entity_name("boiler B2", "asset"), "boiler b2")

    def test_noisy_or_calculation(self):
        confidences = [0.9, 0.8]
        # 1 - (1 - 0.9) * (1 - 0.8) = 1 - 0.1 * 0.2 = 0.98
        self.assertEqual(_calculate_noisy_or(confidences), 0.98)

    def test_alias_merging_and_canonical_naming(self):
        occ_a = EntityOccurrence(
            entity_id="occ-1",
            entity_type="asset",
            canonical_name="P-301",
            original_text="P-301",
            confidence=0.80,
            chunk_id="chk-1",
            document_id=self.doc_id,
            page_index=0,
            metadata={"status": "online"}
        )
        occ_b = EntityOccurrence(
            entity_id="occ-2",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id="chk-2",
            document_id=self.doc_id,
            page_index=0,
            metadata={"model": "Model-X"}
        )
        occ_c = EntityOccurrence(
            entity_id="occ-3",
            entity_type="asset",
            canonical_name="pump p301",
            original_text="pump p301",
            confidence=0.90,
            chunk_id="chk-3",
            document_id=self.doc_id,
            page_index=1,
            metadata={}
        )

        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b, occ_c),
            occurrence_count=3
        )
        rel_col = RelationshipOccurrenceCollection(
            document_id=self.doc_id,
            relationships=(),
            relationship_count=0
        )

        results = resolve_knowledge(entity_col, rel_col)
        self.assertIsInstance(results, ResolvedKnowledgePackage)
        self.assertEqual(len(results.resolved_entities), 1)

        resolved_ent = results.resolved_entities[0]
        # Canonical name should be chosen as the best one: "Pump P-301" (longest/type-qualified)
        self.assertEqual(resolved_ent.canonical_name, "Pump P-301")
        # occurrences tuple should track all 3 occurrence IDs
        self.assertEqual(set(resolved_ent.occurrences), {"occ-1", "occ-2", "occ-3"})
        # Noisy-OR confidence check: 1 - 0.2 * 0.05 * 0.1 = 1 - 0.001 = 0.999
        self.assertEqual(resolved_ent.confidence, 0.999)

    def test_property_conflict_resolution(self):
        occ_a = EntityOccurrence(
            entity_id="occ-1",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="P-301",
            confidence=0.80,
            chunk_id="chk-1",
            document_id=self.doc_id,
            page_index=0,
            metadata={"model": "Model-A", "status": "online"}
        )
        occ_b = EntityOccurrence(
            entity_id="occ-2",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="Pump P-301",
            confidence=0.95,
            chunk_id="chk-2",
            document_id=self.doc_id,
            page_index=0,
            metadata={"model": "Model-B"}  # Higher confidence override
        )

        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_a, occ_b),
            occurrence_count=2
        )
        rel_col = RelationshipOccurrenceCollection(
            document_id=self.doc_id,
            relationships=(),
            relationship_count=0
        )

        results = resolve_knowledge(entity_col, rel_col)
        resolved_properties = results.resolved_entities[0].properties
        # Model-B should override Model-A due to higher confidence
        self.assertEqual(resolved_properties["model"], "Model-B")
        # status should be preserved
        self.assertEqual(resolved_properties["status"], "online")

    def test_relationship_redirection_to_canonical_ids(self):
        # Entity occurrences
        occ_p301 = EntityOccurrence(
            entity_id="occ-p301",
            entity_type="asset",
            canonical_name="Pump P-301",
            original_text="P-301",
            confidence=0.95,
            chunk_id="chk-1",
            document_id=self.doc_id,
            page_index=0,
            metadata={}
        )
        occ_bearing = EntityOccurrence(
            entity_id="occ-bearing",
            entity_type="component",
            canonical_name="bearing",
            original_text="bearing",
            confidence=0.90,
            chunk_id="chk-1",
            document_id=self.doc_id,
            page_index=0,
            metadata={}
        )

        # Relationship occurrences connecting raw occurrence IDs
        rel_occ = RelationshipOccurrence(
            relationship_id="rel-occ-1",
            relationship_type="HAS_COMPONENT",
            source_occurrence_id="occ-p301",
            target_occurrence_id="occ-bearing",
            source_canonical_name="Pump P-301",
            target_canonical_name="bearing",
            confidence=0.95,
            chunk_id="chk-1",
            document_id=self.doc_id,
            page_index=0,
            metadata={}
        )

        entity_col = EntityOccurrenceCollection(
            document_id=self.doc_id,
            occurrences=(occ_p301, occ_bearing),
            occurrence_count=2
        )
        rel_col = RelationshipOccurrenceCollection(
            document_id=self.doc_id,
            relationships=(rel_occ,),
            relationship_count=1
        )

        results = resolve_knowledge(entity_col, rel_col)
        self.assertEqual(len(results.resolved_relationships), 1)
        resolved_rel = results.resolved_relationships[0]

        # Verify redirection to canonical entity IDs
        expected_src_id = results.resolved_entities[0].entity_id if results.resolved_entities[0].entity_type == "asset" else results.resolved_entities[1].entity_id
        expected_tgt_id = results.resolved_entities[1].entity_id if results.resolved_entities[1].entity_type == "component" else results.resolved_entities[0].entity_id
        
        self.assertEqual(resolved_rel.source_entity_id, expected_src_id)
        self.assertEqual(resolved_rel.target_entity_id, expected_tgt_id)
        
        # Verify deterministic ID hash check
        import hashlib
        raw_id = f"has_component_{expected_src_id}_{expected_tgt_id}"
        expected_rel_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
        self.assertEqual(resolved_rel.relationship_id, expected_rel_id)


if __name__ == "__main__":
    unittest.main()
