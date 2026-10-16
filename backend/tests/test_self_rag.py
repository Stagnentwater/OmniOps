"""Unit tests for Self-RAG evidence sufficiency and bounded retry loop (V4 Feature E)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from verification.self_rag import SelfRAGChecker, SufficiencyStatus


class TestSelfRAG(unittest.TestCase):
    """Test suite for Self-RAG evidence sufficiency checks and bounded retrieval."""

    def test_evaluate_sufficiency_empty_chunks(self) -> None:
        """Verify empty context is classified as INSUFFICIENT with targeted secondary query."""
        checker = SelfRAGChecker()
        eval_res = checker.evaluate_sufficiency(
            query="What are the operating limits for pump P-101A?",
            context_chunks=[],
            required_parameters=["pressure", "temperature", "flow"],
        )

        self.assertEqual(eval_res.status, SufficiencyStatus.INSUFFICIENT)
        self.assertEqual(len(eval_res.supported_parameters), 0)
        self.assertIn("P-101A", eval_res.secondary_query)
        self.assertEqual(eval_res.confidence, 0.0)

    def test_evaluate_sufficiency_complete_coverage(self) -> None:
        """Verify context covering required parameters is classified as SUFFICIENT."""
        chunk = MagicMock()
        chunk.text = "Pump P-101A operates at pressure 12 bar, temperature 65 C, and flow 120 m3/h. Isolation valve MOV-101."

        checker = SelfRAGChecker()
        eval_res = checker.evaluate_sufficiency(
            query="Check P-101A specifications",
            context_chunks=[chunk],
            required_parameters=["pressure", "temperature", "flow", "valve"],
        )

        self.assertEqual(eval_res.status, SufficiencyStatus.SUFFICIENT)
        self.assertEqual(len(eval_res.missing_parameters), 0)
        self.assertIsNone(eval_res.secondary_query)
        self.assertEqual(eval_res.confidence, 1.0)

    def test_evaluate_sufficiency_partial_coverage(self) -> None:
        """Verify partial context flags missing parameters and formulates secondary search."""
        chunk = MagicMock()
        chunk.text = "Column C-101 has operating pressure 1.8 bar gauge."

        checker = SelfRAGChecker()
        eval_res = checker.evaluate_sufficiency(
            query="Operating conditions for C-101",
            context_chunks=[chunk],
            required_parameters=["pressure", "temperature", "reflux", "loto"],
        )

        self.assertEqual(eval_res.status, SufficiencyStatus.PARTIALLY_SUFFICIENT)
        self.assertIn("pressure", eval_res.supported_parameters)
        self.assertIn("temperature", eval_res.missing_parameters)
        self.assertIn("C-101", eval_res.secondary_query)

    def test_bounded_secondary_retrieval(self) -> None:
        """Verify Self-RAG executes bounded secondary retrieval and stops when satisfied."""
        initial_chunk = MagicMock()
        initial_chunk.chunk_id = "c1"
        initial_chunk.text = "Exchanger E-102 operating pressure 4.5 bar."

        secondary_chunk = MagicMock()
        secondary_chunk.chunk_id = "c2"
        secondary_chunk.text = "Exchanger E-102 temperature 95 C and isolation valve MOV-204."

        mock_retrieval = MagicMock()
        mock_ret_result = MagicMock()
        mock_ret_result.chunks = [secondary_chunk]
        mock_retrieval.retrieve.return_value = mock_ret_result

        checker = SelfRAGChecker(retrieval_service=mock_retrieval, max_retries=2)
        chunks, eval_res = checker.retrieve_with_sufficiency_check(
            query="Check E-102 conditions",
            initial_chunks=[initial_chunk],
            required_parameters=["pressure", "temperature", "isolation"],
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(eval_res.status, SufficiencyStatus.SUFFICIENT)
        mock_retrieval.retrieve.assert_called_once()

    def test_bounded_retry_limit_enforced(self) -> None:
        """Verify Self-RAG never executes more than max_retries even if evidence remains partial."""
        partial_chunk = MagicMock()
        partial_chunk.chunk_id = "c1"
        partial_chunk.text = "Only pressure 3 bar available."

        mock_retrieval = MagicMock()
        mock_ret_result = MagicMock()
        mock_ret_result.chunks = []  # secondary search returns nothing
        mock_retrieval.retrieve.return_value = mock_ret_result

        checker = SelfRAGChecker(retrieval_service=mock_retrieval, max_retries=2)
        chunks, eval_res = checker.retrieve_with_sufficiency_check(
            query="Exchanger specifications",
            initial_chunks=[partial_chunk],
            required_parameters=["pressure", "temperature", "isolation", "loto", "emergency"],
        )

        # Did not loop indefinitely; executed exactly 1 secondary query (hitting max_retries=2 limit)
        self.assertEqual(eval_res.iteration, 2)
        self.assertNotEqual(eval_res.status, SufficiencyStatus.SUFFICIENT)


if __name__ == "__main__":
    unittest.main()
