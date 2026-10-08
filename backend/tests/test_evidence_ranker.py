"""Deterministic tests for Evidence Ranking (V15-RANK-001).

Tests cover:
- Signal computation correctness
- Ranking order determinism
- Explainable signal output
- Edge cases (empty chunks, no assets, no metadata)
- Ranking does not alter citation provenance
- Weight customization
"""

from __future__ import annotations

import unittest
from retrieval.evidence_ranker import EvidenceRanker, RankingSignals, _DEFAULT_WEIGHTS
from retrieval.retrieval_models import (
    RetrievalContext,
    RetrievedChunk,
    RetrievedEntity,
    RetrievedRelationship,
)


def _make_chunk(
    chunk_id: str = "c1",
    document_id: str = "d1",
    text: str = "Sample text",
    score: float = 0.8,
    page_index: int = 0,
    section: str | None = None,
    metadata: dict | None = None,
) -> RetrievedChunk:
    """Helper to create a RetrievedChunk with defaults."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        score=score,
        page_index=page_index,
        section=section,
        metadata=metadata or {},
    )


def _make_entity(
    entity_id: str = "e1",
    entity_type: str = "Asset",
    canonical_name: str = "Pump P-301",
    properties: dict | None = None,
) -> RetrievedEntity:
    return RetrievedEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        canonical_name=canonical_name,
        properties=properties or {},
    )


def _make_context(
    chunks: tuple[RetrievedChunk, ...] = (),
    entities: tuple[RetrievedEntity, ...] = (),
    relationships: tuple[RetrievedRelationship, ...] = (),
    detected_assets=None,
) -> RetrievalContext:
    return RetrievalContext(
        query="test query",
        chunks=chunks,
        entities=entities,
        relationships=relationships,
        detected_assets=detected_assets,
    )


# ---------------------------------------------------------------------------
# Tests: RankingSignals
# ---------------------------------------------------------------------------

class TestRankingSignals(unittest.TestCase):
    """Verify RankingSignals is frozen and has correct fields."""

    def test_creation(self) -> None:
        signals = RankingSignals(
            semantic_similarity=0.8,
            graph_relevance=1.0,
            asset_match=0.5,
            recency=0.7,
            provenance_completeness=0.6,
            source_priority=0.3,
            final_score=0.65,
        )
        self.assertEqual(signals.semantic_similarity, 0.8)
        self.assertEqual(signals.final_score, 0.65)

    def test_frozen(self) -> None:
        signals = RankingSignals(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        with self.assertRaises(AttributeError):
            signals.final_score = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: Default Weights
# ---------------------------------------------------------------------------

class TestDefaultWeights(unittest.TestCase):
    """Verify weight configuration is valid."""

    def test_weights_sum_to_one(self) -> None:
        total = sum(_DEFAULT_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_all_weights_positive(self) -> None:
        for name, weight in _DEFAULT_WEIGHTS.items():
            self.assertGreater(weight, 0.0, f"Weight {name} must be positive")


# ---------------------------------------------------------------------------
# Tests: Individual Signals
# ---------------------------------------------------------------------------

class TestSemanticSimilaritySignal(unittest.TestCase):
    """Test semantic similarity signal computation."""

    def test_normal_score(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(score=0.85)
        signal = ranker._signal_semantic_similarity(chunk)
        self.assertAlmostEqual(signal, 0.85, places=2)

    def test_clamp_negative(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(score=-0.3)
        signal = ranker._signal_semantic_similarity(chunk)
        self.assertEqual(signal, 0.0)

    def test_clamp_above_one(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(score=1.5)
        signal = ranker._signal_semantic_similarity(chunk)
        self.assertEqual(signal, 1.0)

    def test_zero_score(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(score=0.0)
        signal = ranker._signal_semantic_similarity(chunk)
        self.assertEqual(signal, 0.0)


class TestGraphRelevanceSignal(unittest.TestCase):
    """Test graph relevance signal."""

    def test_document_in_graph(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(document_id="doc-abc")
        signal = ranker._signal_graph_relevance(chunk, {"doc-abc", "doc-xyz"})
        self.assertEqual(signal, 1.0)

    def test_document_not_in_graph(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(document_id="doc-abc")
        signal = ranker._signal_graph_relevance(chunk, {"doc-xyz"})
        self.assertEqual(signal, 0.0)

    def test_empty_graph_ids(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(document_id="doc-abc")
        signal = ranker._signal_graph_relevance(chunk, set())
        self.assertEqual(signal, 0.0)


class TestAssetMatchSignal(unittest.TestCase):
    """Test asset match signal."""

    def test_no_assets_detected(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(text="Pump P-301 maintenance")
        signal = ranker._signal_asset_match(chunk, [])
        self.assertEqual(signal, 0.5)  # Neutral

    def test_one_asset_match(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(text="Pump P-301 requires maintenance")
        signal = ranker._signal_asset_match(chunk, ["Pump P-301"])
        self.assertAlmostEqual(signal, 0.7, places=2)

    def test_multiple_asset_match(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(text="Pump P-301 connects to Valve V-200")
        signal = ranker._signal_asset_match(chunk, ["Pump P-301", "Valve V-200"])
        self.assertEqual(signal, 1.0)

    def test_no_match_in_text(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(text="General maintenance procedures")
        signal = ranker._signal_asset_match(chunk, ["Pump P-301"])
        self.assertEqual(signal, 0.0)


class TestRecencySignal(unittest.TestCase):
    """Test recency signal."""

    def test_with_upload_time(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"upload_time": "2024-01-01T00:00:00Z"})
        signal = ranker._signal_recency(chunk)
        self.assertEqual(signal, 0.7)

    def test_with_document_date(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"document_date": "2024-06-15"})
        signal = ranker._signal_recency(chunk)
        self.assertEqual(signal, 0.7)

    def test_no_date_metadata(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"filename": "test.pdf"})
        signal = ranker._signal_recency(chunk)
        self.assertEqual(signal, 0.5)

    def test_empty_metadata(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={})
        signal = ranker._signal_recency(chunk)
        self.assertEqual(signal, 0.5)


class TestProvenanceCompletenessSignal(unittest.TestCase):
    """Test provenance completeness signal."""

    def test_rich_metadata(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={
            "document_id": "d1",
            "filename": "manual.pdf",
            "section": "Chapter 3",
            "page_index": 5,
            "document_type": "maintenance_manual",
            "source_type": "pdf",
            "upload_time": "2024-01-01",
        })
        signal = ranker._signal_provenance_completeness(chunk)
        self.assertGreaterEqual(signal, 0.8)

    def test_sparse_metadata(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"filename": "test.pdf"})
        signal = ranker._signal_provenance_completeness(chunk)
        self.assertAlmostEqual(signal, 0.2, places=2)

    def test_empty_metadata(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={})
        signal = ranker._signal_provenance_completeness(chunk)
        self.assertEqual(signal, 0.0)


class TestSourcePrioritySignal(unittest.TestCase):
    """Test source priority signal."""

    def test_authority_type(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"document_type": "maintenance_manual"})
        signal = ranker._signal_source_priority(chunk)
        self.assertEqual(signal, 1.0)

    def test_known_non_authority_type(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"document_type": "newsletter"})
        signal = ranker._signal_source_priority(chunk)
        self.assertEqual(signal, 0.5)

    def test_unknown_type(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={})
        signal = ranker._signal_source_priority(chunk)
        self.assertEqual(signal, 0.3)

    def test_source_type_authority(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(metadata={"source_type": "pid"})
        signal = ranker._signal_source_priority(chunk)
        self.assertEqual(signal, 1.0)


# ---------------------------------------------------------------------------
# Tests: Full Ranking Pipeline
# ---------------------------------------------------------------------------

class TestEvidenceRankerRanking(unittest.TestCase):
    """Test the full ranking pipeline."""

    def test_empty_chunks(self) -> None:
        ranker = EvidenceRanker()
        context = _make_context(chunks=())
        ranked, explanations = ranker.rank(context)
        self.assertEqual(ranked, ())
        self.assertEqual(explanations, {})

    def test_single_chunk(self) -> None:
        ranker = EvidenceRanker()
        chunk = _make_chunk(chunk_id="c1", score=0.9)
        context = _make_context(chunks=(chunk,))
        ranked, explanations = ranker.rank(context)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].chunk_id, "c1")
        self.assertIn("c1", explanations)
        self.assertGreater(explanations["c1"].final_score, 0.0)

    def test_ranking_order_by_score(self) -> None:
        """Higher vector similarity should rank higher (all else equal)."""
        ranker = EvidenceRanker()
        c1 = _make_chunk(chunk_id="low", score=0.3, text="generic text")
        c2 = _make_chunk(chunk_id="high", score=0.95, text="generic text")
        context = _make_context(chunks=(c1, c2))

        ranked, explanations = ranker.rank(context)
        self.assertEqual(ranked[0].chunk_id, "high")
        self.assertEqual(ranked[1].chunk_id, "low")
        self.assertGreater(
            explanations["high"].final_score,
            explanations["low"].final_score,
        )

    def test_graph_relevance_boosts_ranking(self) -> None:
        """A chunk from a graph-linked document should rank higher."""
        ranker = EvidenceRanker()

        # Both have same similarity, but c2's document is in the graph
        c1 = _make_chunk(chunk_id="no_graph", document_id="d1", score=0.8)
        c2 = _make_chunk(chunk_id="with_graph", document_id="d2", score=0.8)

        entity = _make_entity(properties={"document_id": "d2"})
        context = _make_context(chunks=(c1, c2), entities=(entity,))

        ranked, explanations = ranker.rank(context)
        self.assertEqual(ranked[0].chunk_id, "with_graph")
        self.assertEqual(explanations["with_graph"].graph_relevance, 1.0)
        self.assertEqual(explanations["no_graph"].graph_relevance, 0.0)

    def test_provenance_does_not_change(self) -> None:
        """Ranking must NOT alter chunk content or citation fields."""
        ranker = EvidenceRanker()
        original = _make_chunk(
            chunk_id="orig",
            document_id="doc-123",
            text="Original evidence text",
            score=0.85,
            page_index=3,
            section="Section 4.2",
            metadata={"filename": "report.pdf"},
        )
        context = _make_context(chunks=(original,))
        ranked, _ = ranker.rank(context)

        result = ranked[0]
        self.assertEqual(result.chunk_id, original.chunk_id)
        self.assertEqual(result.document_id, original.document_id)
        self.assertEqual(result.text, original.text)
        self.assertEqual(result.score, original.score)
        self.assertEqual(result.page_index, original.page_index)
        self.assertEqual(result.section, original.section)
        self.assertEqual(result.metadata, original.metadata)

    def test_deterministic_ranking(self) -> None:
        """Same input produces same ranking every time."""
        ranker = EvidenceRanker()
        chunks = tuple(
            _make_chunk(chunk_id=f"c{i}", score=0.5 + i * 0.1)
            for i in range(5)
        )
        context = _make_context(chunks=chunks)

        # Run ranking 3 times
        results = [ranker.rank(context) for _ in range(3)]

        first_order = [c.chunk_id for c in results[0][0]]
        for ranked, _ in results[1:]:
            self.assertEqual([c.chunk_id for c in ranked], first_order)

    def test_all_signals_present_in_explanation(self) -> None:
        """Every explanation must have all 7 signal fields."""
        ranker = EvidenceRanker()
        chunk = _make_chunk(chunk_id="c1", score=0.7)
        context = _make_context(chunks=(chunk,))
        _, explanations = ranker.rank(context)

        signals = explanations["c1"]
        self.assertIsInstance(signals.semantic_similarity, float)
        self.assertIsInstance(signals.graph_relevance, float)
        self.assertIsInstance(signals.asset_match, float)
        self.assertIsInstance(signals.recency, float)
        self.assertIsInstance(signals.provenance_completeness, float)
        self.assertIsInstance(signals.source_priority, float)
        self.assertIsInstance(signals.final_score, float)

    def test_custom_weights(self) -> None:
        """Custom weights should change ranking behavior."""
        # Weight that ONLY considers graph relevance
        custom_weights = {
            "semantic_similarity": 0.0,
            "graph_relevance": 1.0,
            "asset_match": 0.0,
            "recency": 0.0,
            "provenance_completeness": 0.0,
            "source_priority": 0.0,
        }
        ranker = EvidenceRanker(weights=custom_weights)

        c1 = _make_chunk(chunk_id="high_sim", document_id="d1", score=0.99)
        c2 = _make_chunk(chunk_id="in_graph", document_id="d2", score=0.1)
        entity = _make_entity(properties={"document_id": "d2"})

        context = _make_context(chunks=(c1, c2), entities=(entity,))
        ranked, _ = ranker.rank(context)

        # Despite lower similarity, c2 should rank first due to graph weight
        self.assertEqual(ranked[0].chunk_id, "in_graph")

    def test_authority_type_boost(self) -> None:
        """Maintenance manual should rank above generic documents."""
        ranker = EvidenceRanker()

        c1 = _make_chunk(
            chunk_id="generic", score=0.8,
            metadata={"document_type": "email"},
        )
        c2 = _make_chunk(
            chunk_id="authority", score=0.8,
            metadata={"document_type": "maintenance_manual"},
        )
        context = _make_context(chunks=(c1, c2))
        ranked, explanations = ranker.rank(context)

        self.assertEqual(ranked[0].chunk_id, "authority")
        self.assertGreater(
            explanations["authority"].source_priority,
            explanations["generic"].source_priority,
        )


# ---------------------------------------------------------------------------
# Tests: Helper Methods
# ---------------------------------------------------------------------------

class TestHelperMethods(unittest.TestCase):
    """Test internal helper methods."""

    def test_extract_graph_document_ids(self) -> None:
        ranker = EvidenceRanker()
        entities = (
            _make_entity(properties={"document_id": "d1"}),
            _make_entity(properties={"source_document_id": "d2"}),
            _make_entity(properties={}),
        )
        doc_ids = ranker._extract_graph_document_ids(entities)
        self.assertEqual(doc_ids, {"d1", "d2"})

    def test_extract_graph_document_ids_none(self) -> None:
        ranker = EvidenceRanker()
        doc_ids = ranker._extract_graph_document_ids(None)
        self.assertEqual(doc_ids, set())

    def test_extract_asset_names(self) -> None:
        ranker = EvidenceRanker()
        names = ranker._extract_asset_names(None)
        self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main()
