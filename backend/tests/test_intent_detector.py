"""Unit tests for the IntentDetector (V15-INTENT-001).

Tests cover:
- Each supported intent type with representative queries
- Confidence scoring behavior
- Edge cases (empty queries, ambiguous queries)
- Deterministic classification (same input always produces same output)
- Default fallback to EXPLANATION for unrecognized queries
"""

from __future__ import annotations

import unittest

from retrieval.intent_detector import DetectedIntent, IntentDetector, IntentType


class TestIntentType(unittest.TestCase):
    """Verify the IntentType enum covers all spec'd intents."""

    def test_all_intents_present(self) -> None:
        expected = {
            "maintenance",
            "compliance",
            "asset_lookup",
            "troubleshooting",
            "explanation",
            "summary",
            "timeline",
            "root_cause_analysis",
        }
        actual = {member.value for member in IntentType}
        self.assertEqual(expected, actual)

    def test_intent_string_value(self) -> None:
        self.assertEqual(IntentType.MAINTENANCE.value, "maintenance")
        self.assertEqual(IntentType.ROOT_CAUSE_ANALYSIS.value, "root_cause_analysis")


class TestDetectedIntent(unittest.TestCase):
    """Verify DetectedIntent immutability and structure."""

    def test_frozen_dataclass(self) -> None:
        di = DetectedIntent(
            intent=IntentType.MAINTENANCE,
            confidence=0.8,
            matched_keywords=("maintenance",),
        )
        with self.assertRaises(AttributeError):
            di.intent = IntentType.COMPLIANCE  # type: ignore[misc]


class TestIntentDetectorMaintenance(unittest.TestCase):
    """Maintenance intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_direct_maintenance_query(self) -> None:
        result = self.detector.detect("What is the maintenance schedule for Pump P301?")
        self.assertEqual(result.intent, IntentType.MAINTENANCE)
        self.assertGreater(result.confidence, 0.0)

    def test_preventive_maintenance(self) -> None:
        result = self.detector.detect("Show preventive maintenance procedures")
        self.assertEqual(result.intent, IntentType.MAINTENANCE)

    def test_work_order(self) -> None:
        result = self.detector.detect("Create a new work order for compressor C-100")
        self.assertEqual(result.intent, IntentType.MAINTENANCE)

    def test_spare_part(self) -> None:
        result = self.detector.detect("What spare parts are needed for the overhaul?")
        self.assertEqual(result.intent, IntentType.MAINTENANCE)


class TestIntentDetectorCompliance(unittest.TestCase):
    """Compliance intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_regulation_query(self) -> None:
        result = self.detector.detect("What OSHA regulations apply to this vessel?")
        self.assertEqual(result.intent, IntentType.COMPLIANCE)

    def test_iso_standard(self) -> None:
        result = self.detector.detect("Is this equipment ISO 9001 compliant?")
        self.assertEqual(result.intent, IntentType.COMPLIANCE)

    def test_non_compliance(self) -> None:
        result = self.detector.detect("List all non-compliance issues from the last audit")
        self.assertEqual(result.intent, IntentType.COMPLIANCE)


class TestIntentDetectorAssetLookup(unittest.TestCase):
    """Asset Lookup intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_what_is_query(self) -> None:
        result = self.detector.detect("What is the specifications of Pump P301?")
        self.assertEqual(result.intent, IntentType.ASSET_LOOKUP)

    def test_nameplate_query(self) -> None:
        result = self.detector.detect("Show me the nameplate data for valve V-200")
        self.assertEqual(result.intent, IntentType.ASSET_LOOKUP)

    def test_datasheet_query(self) -> None:
        result = self.detector.detect("Where is the data sheet for this equipment?")
        self.assertEqual(result.intent, IntentType.ASSET_LOOKUP)


class TestIntentDetectorTroubleshooting(unittest.TestCase):
    """Troubleshooting intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_vibration_query(self) -> None:
        result = self.detector.detect("Why is Pump P301 vibrating?")
        self.assertEqual(result.intent, IntentType.TROUBLESHOOTING)

    def test_how_to_fix(self) -> None:
        result = self.detector.detect("How to fix the overheating issue on motor M-50?")
        self.assertEqual(result.intent, IntentType.TROUBLESHOOTING)

    def test_alarm_fault(self) -> None:
        result = self.detector.detect("The alarm tripped on compressor C-100, what is the fault?")
        self.assertEqual(result.intent, IntentType.TROUBLESHOOTING)

    def test_wont_start(self) -> None:
        result = self.detector.detect("Generator G-10 won't start")
        self.assertEqual(result.intent, IntentType.TROUBLESHOOTING)


class TestIntentDetectorExplanation(unittest.TestCase):
    """Explanation intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_how_does_query(self) -> None:
        result = self.detector.detect("How does a centrifugal pump work?")
        self.assertEqual(result.intent, IntentType.EXPLANATION)

    def test_explain_query(self) -> None:
        result = self.detector.detect("Explain the working principle of a heat exchanger")
        self.assertEqual(result.intent, IntentType.EXPLANATION)


class TestIntentDetectorSummary(unittest.TestCase):
    """Summary intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_summary_query(self) -> None:
        result = self.detector.detect("Give me a summary of the inspection report")
        self.assertEqual(result.intent, IntentType.SUMMARY)

    def test_overview_query(self) -> None:
        result = self.detector.detect("Provide an executive summary of maintenance records")
        self.assertEqual(result.intent, IntentType.SUMMARY)


class TestIntentDetectorTimeline(unittest.TestCase):
    """Timeline intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_timeline_query(self) -> None:
        result = self.detector.detect("Show timeline of events for compressor C-100")
        self.assertEqual(result.intent, IntentType.TIMELINE)

    def test_when_did_query(self) -> None:
        result = self.detector.detect("When did the last inspection happen?")
        self.assertEqual(result.intent, IntentType.TIMELINE)

    def test_chronology(self) -> None:
        result = self.detector.detect("What is the chronology of failures this year?")
        self.assertEqual(result.intent, IntentType.TIMELINE)


class TestIntentDetectorRCA(unittest.TestCase):
    """Root Cause Analysis intent classification."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_root_cause_query(self) -> None:
        result = self.detector.detect("What is the root cause of the bearing failure?")
        self.assertEqual(result.intent, IntentType.ROOT_CAUSE_ANALYSIS)

    def test_rca_query(self) -> None:
        result = self.detector.detect("Perform an RCA for the pump seizure incident")
        self.assertEqual(result.intent, IntentType.ROOT_CAUSE_ANALYSIS)

    def test_failure_analysis(self) -> None:
        result = self.detector.detect("Conduct failure analysis on valve V-300")
        self.assertEqual(result.intent, IntentType.ROOT_CAUSE_ANALYSIS)

    def test_five_whys(self) -> None:
        result = self.detector.detect("Apply the 5 whys method to this incident")
        self.assertEqual(result.intent, IntentType.ROOT_CAUSE_ANALYSIS)


class TestIntentDetectorEdgeCases(unittest.TestCase):
    """Edge cases and fallback behavior."""

    def setUp(self) -> None:
        self.detector = IntentDetector()

    def test_empty_query(self) -> None:
        result = self.detector.detect("")
        self.assertEqual(result.intent, IntentType.EXPLANATION)
        self.assertEqual(result.confidence, 0.0)

    def test_whitespace_only(self) -> None:
        result = self.detector.detect("   ")
        self.assertEqual(result.intent, IntentType.EXPLANATION)
        self.assertEqual(result.confidence, 0.0)

    def test_unrecognized_query_defaults_to_explanation(self) -> None:
        result = self.detector.detect("Hello there, how are you?")
        self.assertEqual(result.intent, IntentType.EXPLANATION)

    def test_case_insensitive(self) -> None:
        lower = self.detector.detect("maintenance schedule")
        upper = self.detector.detect("MAINTENANCE SCHEDULE")
        self.assertEqual(lower.intent, upper.intent)

    def test_deterministic(self) -> None:
        """Same query must always produce the same result."""
        query = "Why is Pump P301 vibrating?"
        results = [self.detector.detect(query) for _ in range(10)]
        intents = {r.intent for r in results}
        confidences = {r.confidence for r in results}
        self.assertEqual(len(intents), 1, "Intent must be deterministic")
        self.assertEqual(len(confidences), 1, "Confidence must be deterministic")

    def test_confidence_between_zero_and_one(self) -> None:
        queries = [
            "maintenance schedule for pump",
            "root cause analysis",
            "random gibberish xyz 123",
            "",
        ]
        for q in queries:
            result = self.detector.detect(q)
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 1.0)

    def test_matched_keywords_are_populated(self) -> None:
        result = self.detector.detect("Show maintenance schedule and spare parts needed")
        self.assertEqual(result.intent, IntentType.MAINTENANCE)
        self.assertGreater(len(result.matched_keywords), 0)
        for kw in result.matched_keywords:
            self.assertIsInstance(kw, str)


class TestIntentDetectorSerialization(unittest.TestCase):
    """Verify to_dict serialization matches spec format."""

    def test_to_dict_format(self) -> None:
        detector = IntentDetector()
        result = detector.detect("What is the maintenance schedule?")
        d = detector.to_dict(result)

        self.assertIn("intent", d)
        self.assertIn("confidence", d)
        self.assertIn("matched_keywords", d)
        self.assertEqual(d["intent"], result.intent.value)
        self.assertIsInstance(d["confidence"], float)
        self.assertIsInstance(d["matched_keywords"], list)


class TestIntentDetectorCustomKeywords(unittest.TestCase):
    """Verify constructor accepts custom lexicons for testing."""

    def test_custom_keywords(self) -> None:
        custom = {
            IntentType.MAINTENANCE: {"custom_keyword": 5.0},
        }
        detector = IntentDetector(intent_keywords=custom)
        result = detector.detect("This has a custom_keyword in it")
        self.assertEqual(result.intent, IntentType.MAINTENANCE)


if __name__ == "__main__":
    unittest.main()
