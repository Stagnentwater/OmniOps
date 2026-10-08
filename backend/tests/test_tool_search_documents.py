"""Unit tests for the SearchDocuments tool."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from agents.orchestrator import AgentOrchestrator
from agents.ollama_agent_provider import OllamaChatResponse, OllamaToolCall
from agents.tool_executor import ToolExecutor
from agents.tool_registry import ToolRegistry
from agents.tools.search_documents import SearchDocumentsResult, SearchDocumentsTool
from retrieval.retrieval_models import RetrievedChunk
from retrieval.service import RetrievalService


def _run_async(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


class TestSearchDocumentsDefinition(unittest.TestCase):
    """Tests for SearchDocuments tool definition and schema export."""

    def setUp(self):
        self.mock_retrieval = MagicMock(spec=RetrievalService)
        self.tool = SearchDocumentsTool(self.mock_retrieval)

    def test_definition_properties(self):
        defn = self.tool.definition
        self.assertEqual(defn.name, "search_documents")
        self.assertTrue(len(defn.description) > 20)
        self.assertIn("query", defn.parameters["properties"])
        self.assertIn("limit", defn.parameters["properties"])
        self.assertIn("query", defn.parameters["required"])

    def test_ollama_schema_format(self):
        schema = self.tool.definition.to_ollama_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "search_documents")
        self.assertIn("parameters", schema["function"])


class TestSearchDocumentsExecution(unittest.TestCase):
    """Tests for SearchDocuments execution and argument parsing."""

    def setUp(self):
        self.mock_retrieval = MagicMock(spec=RetrievalService)
        self.tool = SearchDocumentsTool(self.mock_retrieval, default_limit=3)

    def test_missing_query(self):
        result = _run_async(self.tool.execute({}))
        self.assertFalse(result.success)
        self.assertIn("query", result.error)

    def test_empty_string_query(self):
        result = _run_async(self.tool.execute({"query": "   "}))
        self.assertFalse(result.success)
        self.assertIn("query", result.error)

    def test_invalid_argument_type(self):
        result = _run_async(self.tool.execute("not a dict"))  # type: ignore
        self.assertFalse(result.success)
        self.assertIn("dictionary", result.error)

    def test_successful_search_with_chunks(self):
        sample_chunks = [
            RetrievedChunk(
                chunk_id="chunk-1",
                document_id="pumps_manual.pdf",
                text="Pump P-101 operates at 45 psi under normal load.",
                score=0.92,
                page_index=14,
                section="Operating Pressures",
                metadata={"type": "manual"},
            ),
            RetrievedChunk(
                chunk_id="chunk-2",
                document_id="pumps_manual.pdf",
                text="Emergency shutdown occurs if pressure exceeds 60 psi.",
                score=0.85,
                page_index=15,
                section="Emergency Limits",
                metadata={"type": "manual"},
            ),
        ]
        self.mock_retrieval._retrieve_vectors.return_value = sample_chunks

        result = _run_async(self.tool.execute({"query": "operating pressure of P-101", "limit": 2}))

        self.assertTrue(result.success)
        self.mock_retrieval._retrieve_vectors.assert_called_once_with(
            query="operating pressure of P-101",
            limit=2,
        )
        self.assertIsInstance(result.result, SearchDocumentsResult)
        self.assertIn("pumps_manual.pdf", str(result.result))
        self.assertIn("Page: 14", str(result.result))
        self.assertIn("Pump P-101 operates at 45 psi", str(result.result))
        self.assertEqual(len(result.result.chunks), 2)
        self.assertEqual(result.result.chunks[0].chunk_id, "chunk-1")

    def test_empty_search_results(self):
        self.mock_retrieval._retrieve_vectors.return_value = []

        result = _run_async(self.tool.execute({"query": "nonexistent term"}))

        self.assertTrue(result.success)
        self.assertIn("No document chunks found", str(result.result))
        self.assertEqual(len(result.result.chunks), 0)

    def test_limit_clamping_and_fallback(self):
        self.mock_retrieval._retrieve_vectors.return_value = []

        # Negative limit falls back to default_limit (3)
        _run_async(self.tool.execute({"query": "test", "limit": -5}))
        self.mock_retrieval._retrieve_vectors.assert_called_with(query="test", limit=3)

        # Invalid string limit falls back to default_limit
        _run_async(self.tool.execute({"query": "test", "limit": "invalid"}))
        self.mock_retrieval._retrieve_vectors.assert_called_with(query="test", limit=3)

        # Limit > 20 is capped to 20
        _run_async(self.tool.execute({"query": "test", "limit": 50}))
        self.mock_retrieval._retrieve_vectors.assert_called_with(query="test", limit=20)

    def test_retrieval_exception_handled_gracefully(self):
        self.mock_retrieval._retrieve_vectors.side_effect = RuntimeError("Qdrant connection timed out")

        result = _run_async(self.tool.execute({"query": "fatal query"}))

        self.assertFalse(result.success)
        self.assertIn("Vector retrieval failed", result.error)
        self.assertIn("Qdrant connection timed out", result.error)


class TestSearchDocumentsIntegration(unittest.TestCase):
    """Tests for SearchDocuments through ToolRegistry, ToolExecutor, and AgentOrchestrator."""

    def test_registry_and_executor(self):
        mock_retrieval = MagicMock(spec=RetrievalService)
        mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="c1",
                document_id="safety.pdf",
                text="Always wear PPE in unit 4.",
                score=0.95,
                page_index=1,
                section="Safety Rules",
                metadata={},
            )
        ]

        tool = SearchDocumentsTool(mock_retrieval)
        registry = ToolRegistry()
        registry.register(tool)

        self.assertIn("search_documents", registry)
        executor = ToolExecutor(registry)

        tool_result = _run_async(executor.execute("search_documents", {"query": "PPE requirements"}))

        self.assertTrue(tool_result.success)
        self.assertIn("safety.pdf", str(tool_result.result))
        self.assertIn("wear PPE", str(tool_result.result))

    def test_orchestrator_loop_with_search_tool(self):
        mock_retrieval = MagicMock(spec=RetrievalService)
        mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="c1",
                document_id="compressor.pdf",
                text="Turbine inlet pressure rating is 120 bar.",
                score=0.91,
                page_index=5,
                section="Specifications",
                metadata={},
            )
        ]

        tool = SearchDocumentsTool(mock_retrieval)
        registry = ToolRegistry()
        registry.register(tool)
        executor = ToolExecutor(registry)

        # Mock LLM provider:
        # Turn 1: decides to call search_documents
        # Turn 2: answers using search results
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_documents",
                        arguments={"query": "turbine inlet pressure"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="The turbine inlet pressure rating is 120 bar according to compressor.pdf.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_iterations=5,
        )

        agent_result = orchestrator.run("What is the turbine inlet pressure?")

        self.assertIsNotNone(agent_result.answer)
        self.assertIn("120 bar", agent_result.answer)
        self.assertEqual(agent_result.iterations, 2)
        self.assertEqual(len(agent_result.tool_calls_made), 1)
        self.assertEqual(agent_result.tool_calls_made[0]["tool"], "search_documents")
        self.assertEqual(agent_result.tool_calls_made[0]["arguments"]["query"], "turbine inlet pressure")


if __name__ == "__main__":
    unittest.main()
