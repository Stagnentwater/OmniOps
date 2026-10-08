"""Unit tests for the AssetDetector (V15-ASSET-001).

Tests cover:
- Regex extraction of asset mentions (full names, tags, components)
- Graph resolution of known assets
- Handling of unknown/ambiguous assets
- Deduplication of candidates
- Edge cases (empty queries, no mentions)
- Deterministic classification
"""

from __future__ import annotations

import unittest

from retrieval.asset_detector import (
    AssetCandidate,
    AssetDetectionResult,
    AssetDetector,
)
from graph.query_service import GraphQueryService
from graph.repository import GraphRepository


# ---------------------------------------------------------------------------
# Test Fakes
# ---------------------------------------------------------------------------

class FakeGraphRepository(GraphRepository):
    """In-memory graph repository for testing asset resolution."""

    def __init__(self, nodes: list[dict] | None = None) -> None:
        self._nodes = nodes or []

    def persist_knowledge_package(self, package) -> None:
        pass

    def delete_document(self, document_id: str) -> None:
        pass

    def get_entity(self, entity_id: str) -> dict | None:
        for n in self._nodes:
            if n.get("entity_id") == entity_id:
                return n
        return None

    def get_neighbors(self, entity_id, relationship_type=None, direction="both"):
        return []

    def traverse(self, entity_id, relationship_types=None, max_depth=1):
        return []

    def expand_subgraph(self, entity_id, max_depth=2):
        return {"center": None, "nodes": [], "edges": []}

    def search_nodes(self, query: str, limit: int = 5) -> list[dict]:
        """Search by substring match on canonical_name."""
        results = []
        q_lower = query.lower()
        for node in self._nodes:
            name = node.get("canonical_name", "").lower()
            if q_lower in name or name in q_lower:
                results.append(node)
        return results[:limit]


# ---------------------------------------------------------------------------
# Tests: Mention Extraction (no graph needed)
# ---------------------------------------------------------------------------

class TestAssetDetectorExtraction(unittest.TestCase):
    """Test regex-based asset mention extraction without graph resolution."""

    def setUp(self) -> None:
        # No graph service → all candidates will be unresolved
        self.detector = AssetDetector(graph_service=None)

    def test_full_asset_mention(self) -> None:
        result = self.detector.detect("Why is Pump P301 vibrating?")
        self.assertEqual(len(result.candidates), 1)
        self.assertIn("Pump P301", result.candidates[0].raw_mention)
        self.assertFalse(result.candidates[0].resolved)

    def test_multiple_assets(self) -> None:
        result = self.detector.detect(
            "Connect Valve V-200 to Compressor C100"
        )
        self.assertGreaterEqual(len(result.candidates), 2)
        raw_mentions = {c.raw_mention for c in result.candidates}
        self.assertTrue(
            any("Valve" in m for m in raw_mentions),
            f"Expected Valve mention in {raw_mentions}",
        )
        self.assertTrue(
            any("Compressor" in m for m in raw_mentions),
            f"Expected Compressor mention in {raw_mentions}",
        )

    def test_tag_pattern(self) -> None:
        result = self.detector.detect("Check status of P-301")
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].raw_mention, "P-301")
        self.assertEqual(result.candidates[0].entity_type, "tag")

    def test_component_mention(self) -> None:
        result = self.detector.detect("The bearing is worn out")
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].raw_mention, "bearing")
        self.assertEqual(result.candidates[0].entity_type, "component")

    def test_no_mentions(self) -> None:
        result = self.detector.detect("What is the weather today?")
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(result.resolved_count, 0)
        self.assertFalse(result.ambiguous)

    def test_empty_query(self) -> None:
        result = self.detector.detect("")
        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(result.resolved_count, 0)

    def test_whitespace_only(self) -> None:
        result = self.detector.detect("   ")
        self.assertEqual(len(result.candidates), 0)

    def test_case_insensitive_extraction(self) -> None:
        result = self.detector.detect("PUMP p301 is down")
        self.assertEqual(len(result.candidates), 1)
        self.assertIn("PUMP", result.candidates[0].raw_mention)

    def test_no_duplicate_extraction(self) -> None:
        """Same asset mentioned twice should only produce one mention."""
        result = self.detector.detect(
            "Pump P301 is connected to Pump P301"
        )
        # Regex finds two matches but dedup by normalized text should keep one
        raw_mentions = [c.raw_mention.lower() for c in result.candidates]
        # Should have at most one "pump p301" entry
        self.assertEqual(
            raw_mentions.count("pump p301"),
            1,
            f"Expected exactly 1 'pump p301' but got {raw_mentions}",
        )


# ---------------------------------------------------------------------------
# Tests: Graph Resolution
# ---------------------------------------------------------------------------

class TestAssetDetectorResolution(unittest.TestCase):
    """Test asset resolution against a fake Knowledge Graph."""

    def setUp(self) -> None:
        self.graph_nodes = [
            {
                "entity_id": "asset-001",
                "entity_type": "asset",
                "canonical_name": "Pump P301",
                "confidence": 0.95,
            },
            {
                "entity_id": "asset-002",
                "entity_type": "asset",
                "canonical_name": "Valve V-200",
                "confidence": 0.90,
            },
            {
                "entity_id": "comp-001",
                "entity_type": "component",
                "canonical_name": "Bearing",
                "confidence": 0.85,
            },
        ]
        repo = FakeGraphRepository(nodes=self.graph_nodes)
        graph_service = GraphQueryService(repo)
        self.detector = AssetDetector(graph_service=graph_service)

    def test_resolved_asset(self) -> None:
        result = self.detector.detect("Why is Pump P301 vibrating?")
        self.assertGreater(result.resolved_count, 0)
        resolved = [c for c in result.candidates if c.resolved]
        self.assertTrue(len(resolved) >= 1)
        self.assertEqual(resolved[0].entity_id, "asset-001")
        self.assertEqual(resolved[0].canonical_name, "Pump P301")

    def test_resolved_confidence(self) -> None:
        result = self.detector.detect("Valve V-200 is leaking")
        resolved = [c for c in result.candidates if c.resolved]
        self.assertTrue(len(resolved) >= 1)
        self.assertGreater(resolved[0].confidence, 0.0)
        self.assertLessEqual(resolved[0].confidence, 1.0)

    def test_unresolved_asset_preserves_fallback(self) -> None:
        """Assets not found in the graph should still appear as unresolved candidates."""
        result = self.detector.detect("Check Generator G-500")
        self.assertEqual(result.resolved_count, 0)
        # The mention should still be present as an unresolved candidate
        self.assertGreaterEqual(len(result.candidates), 1)
        self.assertFalse(result.candidates[0].resolved)
        self.assertIsNone(result.candidates[0].entity_id)

    def test_component_resolution(self) -> None:
        result = self.detector.detect("The bearing needs replacement")
        # Should find the component in the graph
        resolved = [c for c in result.candidates if c.resolved]
        self.assertTrue(len(resolved) >= 1)
        self.assertEqual(resolved[0].entity_id, "comp-001")

    def test_mixed_resolved_and_unresolved(self) -> None:
        """Query with both a known and unknown asset."""
        result = self.detector.detect(
            "Connect Pump P301 to Turbine T-999"
        )
        resolved = [c for c in result.candidates if c.resolved]
        unresolved = [c for c in result.candidates if not c.resolved]
        self.assertGreater(len(resolved), 0, "Known asset should resolve")
        self.assertGreater(len(unresolved), 0, "Unknown asset should remain unresolved")


# ---------------------------------------------------------------------------
# Tests: Ambiguity
# ---------------------------------------------------------------------------

class TestAssetDetectorAmbiguity(unittest.TestCase):
    """Test handling of ambiguous matches."""

    def setUp(self) -> None:
        # Two nodes with overlapping names
        self.graph_nodes = [
            {
                "entity_id": "asset-010",
                "entity_type": "asset",
                "canonical_name": "Motor M-50",
                "confidence": 0.90,
            },
            {
                "entity_id": "asset-011",
                "entity_type": "asset",
                "canonical_name": "Motor M-500",
                "confidence": 0.85,
            },
        ]
        repo = FakeGraphRepository(nodes=self.graph_nodes)
        graph_service = GraphQueryService(repo)
        self.detector = AssetDetector(graph_service=graph_service)

    def test_ambiguous_flag_set(self) -> None:
        result = self.detector.detect("Check Motor M-50")
        if len([c for c in result.candidates if c.resolved]) > 1:
            self.assertTrue(result.ambiguous)


# ---------------------------------------------------------------------------
# Tests: Deduplication
# ---------------------------------------------------------------------------

class TestAssetDetectorDeduplication(unittest.TestCase):
    """Test deduplication of resolved candidates."""

    def test_highest_confidence_kept(self) -> None:
        candidates = [
            AssetCandidate(
                raw_mention="Pump P301",
                entity_id="asset-001",
                canonical_name="Pump P301",
                entity_type="asset",
                confidence=0.9,
                resolved=True,
            ),
            AssetCandidate(
                raw_mention="Pump P301",
                entity_id="asset-001",
                canonical_name="Pump P301",
                entity_type="asset",
                confidence=0.7,
                resolved=True,
            ),
        ]
        detector = AssetDetector(graph_service=None)
        deduped = detector._deduplicate_candidates(candidates)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].confidence, 0.9)

    def test_unresolved_always_kept(self) -> None:
        candidates = [
            AssetCandidate(
                raw_mention="Unknown X-99",
                entity_id=None,
                canonical_name="Unknown X-99",
                entity_type="tag",
                confidence=0.0,
                resolved=False,
            ),
        ]
        detector = AssetDetector(graph_service=None)
        deduped = detector._deduplicate_candidates(candidates)
        self.assertEqual(len(deduped), 1)
        self.assertFalse(deduped[0].resolved)


# ---------------------------------------------------------------------------
# Tests: Serialization
# ---------------------------------------------------------------------------

class TestAssetDetectorSerialization(unittest.TestCase):
    """Test to_dict serialization."""

    def test_to_dict_format(self) -> None:
        detector = AssetDetector(graph_service=None)
        result = detector.detect("Pump P301 status")
        d = detector.to_dict(result)

        self.assertIn("candidates", d)
        self.assertIn("resolved_count", d)
        self.assertIn("ambiguous", d)
        self.assertIsInstance(d["candidates"], list)
        if d["candidates"]:
            cand = d["candidates"][0]
            self.assertIn("raw_mention", cand)
            self.assertIn("entity_id", cand)
            self.assertIn("canonical_name", cand)
            self.assertIn("entity_type", cand)
            self.assertIn("confidence", cand)
            self.assertIn("resolved", cand)


# ---------------------------------------------------------------------------
# Tests: Determinism
# ---------------------------------------------------------------------------

class TestAssetDetectorDeterminism(unittest.TestCase):
    """Verify deterministic behavior."""

    def test_same_input_same_output(self) -> None:
        detector = AssetDetector(graph_service=None)
        query = "Why is Pump P301 vibrating?"
        results = [detector.detect(query) for _ in range(10)]

        counts = {len(r.candidates) for r in results}
        self.assertEqual(len(counts), 1, "Candidate count must be deterministic")

        if results[0].candidates:
            mentions = {r.candidates[0].raw_mention for r in results}
            self.assertEqual(len(mentions), 1, "Raw mention must be deterministic")


# ---------------------------------------------------------------------------
# Tests: Frozen dataclass
# ---------------------------------------------------------------------------

class TestAssetCandidateImmutability(unittest.TestCase):
    """Verify AssetCandidate is immutable."""

    def test_frozen(self) -> None:
        c = AssetCandidate(
            raw_mention="Pump P301",
            entity_id="x",
            canonical_name="Pump P301",
            entity_type="asset",
            confidence=0.9,
            resolved=True,
        )
        with self.assertRaises(AttributeError):
            c.confidence = 0.5  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
