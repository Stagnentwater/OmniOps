"""Unit tests for the SearchKnowledgeGraph tool."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from agents.orchestrator import AgentOrchestrator
from agents.ollama_agent_provider import OllamaChatResponse, OllamaToolCall
from agents.tool_executor import ToolExecutor
from agents.tool_registry import ToolRegistry
from agents.tools.search_graph import SearchGraphResult, SearchKnowledgeGraphTool
from graph.query_service import GraphQueryService


def _run_async(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


class TestSearchGraphDefinition(unittest.TestCase):
    """Tests for SearchKnowledgeGraph tool definition and schema export."""

    def setUp(self):
        self.mock_graph = MagicMock(spec=GraphQueryService)
        self.tool = SearchKnowledgeGraphTool(self.mock_graph)

    def test_definition_properties(self):
        defn = self.tool.definition
        self.assertEqual(defn.name, "search_knowledge_graph")
        self.assertTrue(len(defn.description) > 20)
        self.assertIn("query", defn.parameters["properties"])
        self.assertIn("entity_id", defn.parameters["properties"])
        self.assertIn("expand_depth", defn.parameters["properties"])
        self.assertIn("limit", defn.parameters["properties"])

    def test_ollama_schema_format(self):
        schema = self.tool.definition.to_ollama_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "search_knowledge_graph")
        self.assertIn("parameters", schema["function"])


class TestSearchGraphExecution(unittest.TestCase):
    """Tests for SearchKnowledgeGraph argument parsing and graph calls."""

    def setUp(self):
        self.mock_graph = MagicMock(spec=GraphQueryService)
        self.tool = SearchKnowledgeGraphTool(self.mock_graph, default_limit=3, default_depth=1)

    def test_missing_both_query_and_entity_id(self):
        result = _run_async(self.tool.execute({}))
        self.assertFalse(result.success)
        self.assertIn("At least one", result.error)

    def test_whitespace_query_and_no_entity_id(self):
        result = _run_async(self.tool.execute({"query": "   "}))
        self.assertFalse(result.success)
        self.assertIn("At least one", result.error)

    def test_invalid_argument_type(self):
        result = _run_async(self.tool.execute("not a dict"))  # type: ignore
        self.assertFalse(result.success)
        self.assertIn("dictionary", result.error)

    def test_search_by_query_with_expansion(self):
        sample_nodes = [
            {
                "entity_id": "ent-p101",
                "canonical_name": "P-101",
                "entity_type": "Pump",
                "document_id": "pumps.pdf",
                "manufacturer": "Flowserve",
            }
        ]
        sample_subgraph = {
            "center": sample_nodes[0],
            "nodes": [
                sample_nodes[0],
                {
                    "entity_id": "ent-v102",
                    "canonical_name": "V-102",
                    "entity_type": "Vessel",
                },
            ],
            "edges": [
                {
                    "relationship_type": "CONNECTED_TO",
                    "source_entity_id": "P-101",
                    "target_entity_id": "V-102",
                }
            ],
        }

        self.mock_graph.search_nodes.return_value = sample_nodes
        self.mock_graph.expand_subgraph.return_value = sample_subgraph

        result = _run_async(self.tool.execute({"query": "P-101", "limit": 2, "expand_depth": 1}))

        self.assertTrue(result.success)
        self.mock_graph.search_nodes.assert_called_once_with(query="P-101", limit=2)
        self.mock_graph.expand_subgraph.assert_called_once_with(entity_id="ent-p101", max_depth=1)

        self.assertIsInstance(result.result, SearchGraphResult)
        self.assertIn("P-101", str(result.result))
        self.assertIn("V-102", str(result.result))
        self.assertIn("CONNECTED_TO", str(result.result))
        self.assertEqual(len(result.result.entities), 2)
        self.assertEqual(len(result.result.edges), 1)

    def test_search_by_entity_id_direct_expansion(self):
        sample_subgraph = {
            "center": {
                "entity_id": "ent-hex10",
                "canonical_name": "E-101",
                "entity_type": "HeatExchanger",
            },
            "nodes": [
                {
                    "entity_id": "ent-hex10",
                    "canonical_name": "E-101",
                    "entity_type": "HeatExchanger",
                },
                {
                    "entity_id": "ent-area1",
                    "canonical_name": "Unit 100",
                    "entity_type": "Area",
                },
            ],
            "edges": [
                {
                    "relationship_type": "LOCATED_IN",
                    "source_entity_id": "E-101",
                    "target_entity_id": "Unit 100",
                }
            ],
        }
        self.mock_graph.expand_subgraph.return_value = sample_subgraph

        result = _run_async(self.tool.execute({"entity_id": "ent-hex10", "expand_depth": 2}))

        self.assertTrue(result.success)
        self.mock_graph.expand_subgraph.assert_called_once_with(entity_id="ent-hex10", max_depth=2)
        self.mock_graph.search_nodes.assert_not_called()

        self.assertIn("E-101", str(result.result))
        self.assertIn("LOCATED_IN", str(result.result))
        self.assertEqual(len(result.result.edges), 1)

    def test_empty_search_results(self):
        self.mock_graph.search_nodes.return_value = []

        result = _run_async(self.tool.execute({"query": "nonexistent_pump"}))

        self.assertTrue(result.success)
        self.assertIn("No entities or relationships found", str(result.result))
        self.assertEqual(len(result.result.entities), 0)
        self.assertEqual(len(result.result.edges), 0)

    def test_limit_and_depth_clamping(self):
        self.mock_graph.search_nodes.return_value = []

        # Negative limit and depth fall back to defaults
        _run_async(self.tool.execute({"query": "test", "limit": -1, "expand_depth": -1}))
        self.mock_graph.search_nodes.assert_called_with(query="test", limit=3)

        # High limit capped to 15, high depth capped to 2
        sample_node = [{"entity_id": "e1", "canonical_name": "N1"}]
        self.mock_graph.search_nodes.return_value = sample_node
        self.mock_graph.expand_subgraph.return_value = {"nodes": [], "edges": []}

        _run_async(self.tool.execute({"query": "test", "limit": 100, "expand_depth": 10}))
        self.mock_graph.search_nodes.assert_called_with(query="test", limit=15)
        self.mock_graph.expand_subgraph.assert_called_with(entity_id="e1", max_depth=2)

    def test_graph_exception_handled_gracefully(self):
        self.mock_graph.search_nodes.side_effect = RuntimeError("Neo4j Bolt connection dropped")

        result = _run_async(self.tool.execute({"query": "crash query"}))

        self.assertFalse(result.success)
        self.assertIn("Knowledge Graph query failed", result.error)
        self.assertIn("Neo4j Bolt connection dropped", result.error)


class TestSearchGraphIntegration(unittest.TestCase):
    """Tests for SearchKnowledgeGraph with Registry, Executor, and Orchestrator."""

    def test_registry_and_executor(self):
        mock_graph = MagicMock(spec=GraphQueryService)
        mock_graph.search_nodes.return_value = [
            {"entity_id": "e1", "canonical_name": "TK-101", "entity_type": "Tank"}
        ]
        mock_graph.expand_subgraph.return_value = {
            "nodes": [{"entity_id": "e1", "canonical_name": "TK-101"}],
            "edges": [],
        }

        tool = SearchKnowledgeGraphTool(mock_graph)
        registry = ToolRegistry()
        registry.register(tool)

        self.assertIn("search_knowledge_graph", registry)
        executor = ToolExecutor(registry)

        tool_result = _run_async(executor.execute("search_knowledge_graph", {"query": "TK-101"}))

        self.assertTrue(tool_result.success)
        self.assertIn("TK-101", str(tool_result.result))

    def test_orchestrator_loop_with_graph_tool(self):
        mock_graph = MagicMock(spec=GraphQueryService)
        mock_graph.search_nodes.return_value = [
            {"entity_id": "e1", "canonical_name": "P-101", "entity_type": "Pump"}
        ]
        mock_graph.expand_subgraph.return_value = {
            "nodes": [
                {"entity_id": "e1", "canonical_name": "P-101", "entity_type": "Pump"},
                {"entity_id": "e2", "canonical_name": "V-102", "entity_type": "Vessel"},
            ],
            "edges": [
                {
                    "relationship_type": "CONNECTED_TO",
                    "source_entity_id": "P-101",
                    "target_entity_id": "V-102",
                }
            ],
        }

        tool = SearchKnowledgeGraphTool(mock_graph)
        registry = ToolRegistry()
        registry.register(tool)
        executor = ToolExecutor(registry)

        mock_llm = MagicMock()
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_knowledge_graph",
                        arguments={"query": "P-101 connections"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="According to the knowledge graph, Pump P-101 is connected to Vessel V-102.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_iterations=5,
        )

        agent_result = orchestrator.run("What equipment is connected to P-101?")

        self.assertIsNotNone(agent_result.answer)
        self.assertIn("Vessel V-102", agent_result.answer)
        self.assertEqual(agent_result.iterations, 2)
        self.assertEqual(len(agent_result.tool_calls_made), 1)
        self.assertEqual(agent_result.tool_calls_made[0]["tool"], "search_knowledge_graph")
        self.assertEqual(agent_result.tool_calls_made[0]["arguments"]["query"], "P-101 connections")


if __name__ == "__main__":
    unittest.main()
