"""Tests for multi-tool orchestration across the agentic framework.

Validates that the AgentOrchestrator can chain multiple tools in sequence
based on dynamically evolving state:
1. SearchDocuments → Calculate (extract numbers from SOP/spec, then compute)
2. SearchDocuments → SearchKnowledgeGraph (extract asset from document, look up topology)
3. SearchKnowledgeGraph → Calculate (look up asset property in graph, compute threshold)
4. Dynamic tool branching based on intermediate results
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from agents.orchestrator import AgentOrchestrator, AgentResult
from agents.ollama_agent_provider import OllamaAgentProvider, OllamaChatResponse, OllamaToolCall
from agents.tool_executor import ToolExecutor
from agents.tool_registry import ToolRegistry
from agents.tools.calculate import CalculateTool
from agents.tools.search_documents import SearchDocumentsTool
from agents.tools.search_graph import SearchKnowledgeGraphTool
from calculation.service import CalculationService
from calculation.subprocess_sandbox import SubprocessSandboxProvider
from calculation.validator import CodeValidator
from graph.query_service import GraphQueryService
from retrieval.retrieval_models import RetrievedChunk
from retrieval.service import RetrievalService


class TestMultiToolOrchestration(unittest.TestCase):
    """Integration tests for multi-tool execution chains."""

    def setUp(self):
        # 1. Setup mocked RetrievalService for SearchDocumentsTool
        self.mock_retrieval = MagicMock(spec=RetrievalService)
        self.doc_tool = SearchDocumentsTool(self.mock_retrieval)

        # 2. Setup mocked GraphQueryService for SearchKnowledgeGraphTool
        self.mock_graph = MagicMock(spec=GraphQueryService)
        self.graph_tool = SearchKnowledgeGraphTool(self.mock_graph)

        # 3. Setup real CalculationService for CalculateTool
        self.calc_service = CalculationService(
            sandbox=SubprocessSandboxProvider(),
            validator=CodeValidator(),
            timeout_seconds=5.0,
            model_name="llama3.2",
        )
        self.calc_tool = CalculateTool(self.calc_service)

        # 4. Populate ToolRegistry with all 3 tools
        self.registry = ToolRegistry()
        self.registry.register(self.doc_tool)
        self.registry.register(self.graph_tool)
        self.registry.register(self.calc_tool)

        self.executor = ToolExecutor(self.registry)

    def test_search_then_calculate_chain(self):
        """Test: Search retrieves operational data, then Calculate computes heat duty."""
        # Mock retrieval returning equipment specification chunk
        self.mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="chunk-e101",
                document_id="heat_exchangers_manual.pdf",
                text="Exchanger E-101 design specs: mass flow = 25.0 kg/s, cp = 4.18 kJ/kg.K, delta_T = 30.0 K.",
                score=0.94,
                page_index=12,
                section="Design Basis",
                metadata={"equipment": "E-101"},
            )
        ]

        # LLM Multi-step Behavior:
        # Step 1: Decision to search documents for E-101 specifications
        # Step 2: Decision to calculate duty using extracted parameters (25 * 4.18 * 30 = 3135.0)
        # Step 3: Synthesis of final answer
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_documents",
                        arguments={"query": "Exchanger E-101 design specs flow cp delta_T"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": "25.0 * 4.18 * 30.0"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="Based on the specifications in heat_exchangers_manual.pdf, the design heat duty for Exchanger E-101 is 3135.0 kW.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=self.registry,
            tool_executor=self.executor,
            max_iterations=6,
        )

        result: AgentResult = orchestrator.run("What is the design heat duty of Exchanger E-101?")

        self.assertIsNotNone(result.answer)
        self.assertIn("3135.0 kW", result.answer)
        self.assertEqual(result.iterations, 3)
        self.assertEqual(len(result.tool_calls_made), 2)
        
        # Verify tool chain order
        self.assertEqual(result.tool_calls_made[0]["tool"], "search_documents")
        self.assertEqual(result.tool_calls_made[1]["tool"], "calculate")

    def test_search_then_graph_chain(self):
        """Test: Search retrieves incident record, Graph explores equipment connectivity."""
        # 1. Search returns incident summary with asset name
        self.mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="chunk-ir402",
                document_id="incident_log_2026.pdf",
                text="Incident IR-402: High vibration shutdown on Booster Pump P-204.",
                score=0.91,
                page_index=3,
                section="Monthly Incidents",
                metadata={"incident_id": "IR-402"},
            )
        ]

        # 2. Graph returns topology for P-204
        self.mock_graph.search_nodes.return_value = [
            {
                "entity_id": "ent-p204",
                "canonical_name": "P-204",
                "entity_type": "Pump",
            }
        ]
        self.mock_graph.expand_subgraph.return_value = {
            "center": {"entity_id": "ent-p204", "canonical_name": "P-204"},
            "nodes": [
                {"entity_id": "ent-p204", "canonical_name": "P-204"},
                {"entity_id": "ent-tk101", "canonical_name": "TK-101", "entity_type": "Tank"},
                {"entity_id": "ent-v301", "canonical_name": "V-301", "entity_type": "Vessel"},
            ],
            "edges": [
                {"relationship_type": "FEEDS", "source_entity_id": "TK-101", "target_entity_id": "P-204"},
                {"relationship_type": "DISCHARGES_TO", "source_entity_id": "P-204", "target_entity_id": "V-301"},
            ],
        }

        # Multi-step LLM conversation
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_documents",
                        arguments={"query": "Incident IR-402 equipment involved"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_knowledge_graph",
                        arguments={"query": "P-204"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="Incident IR-402 involved Booster Pump P-204. In the plant network, P-204 is fed by Tank TK-101 and discharges to Vessel V-301.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=self.registry,
            tool_executor=self.executor,
            max_iterations=6,
        )

        result: AgentResult = orchestrator.run("Which equipment failed in Incident IR-402 and what are its plant connections?")

        self.assertIsNotNone(result.answer)
        self.assertIn("P-204", result.answer)
        self.assertIn("TK-101", result.answer)
        self.assertIn("V-301", result.answer)
        self.assertEqual(result.iterations, 3)
        self.assertEqual(len(result.tool_calls_made), 2)
        self.assertEqual(result.tool_calls_made[0]["tool"], "search_documents")
        self.assertEqual(result.tool_calls_made[1]["tool"], "search_knowledge_graph")

    def test_graph_then_calculate_chain(self):
        """Test: Graph retrieves equipment capacity property, Calculate computes alarm limit."""
        # 1. Graph returns tank entity with volume property
        self.mock_graph.search_nodes.return_value = [
            {
                "entity_id": "ent-tk500",
                "canonical_name": "TK-500",
                "entity_type": "StorageTank",
                "capacity_m3": 8500.0,
            }
        ]
        self.mock_graph.expand_subgraph.return_value = {"nodes": [], "edges": []}

        # LLM multi-step execution: Graph lookup -> Calculate 85% high alarm level (8500 * 0.85 = 7225.0)
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_knowledge_graph",
                        arguments={"query": "TK-500 capacity"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": "8500.0 * 0.85"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="Storage Tank TK-500 has a capacity of 8,500 m³. The 85% high level alarm is set at 7225.0 m³.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=self.registry,
            tool_executor=self.executor,
            max_iterations=6,
        )

        result: AgentResult = orchestrator.run("What is the 85% high-level alarm volume for Tank TK-500?")

        self.assertIsNotNone(result.answer)
        self.assertIn("7225.0", result.answer)
        self.assertEqual(result.iterations, 3)
        self.assertEqual(len(result.tool_calls_made), 2)
        self.assertEqual(result.tool_calls_made[0]["tool"], "search_knowledge_graph")
        self.assertEqual(result.tool_calls_made[1]["tool"], "calculate")


if __name__ == "__main__":
    unittest.main()
