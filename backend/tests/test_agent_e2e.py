"""End-to-end validation test suite for OmniOps agentic system (AGENT-E2E-001).

Validates all 7 end-to-end scenarios required by Phase 16:
1. No-tool query ("Hello") → direct answer without tool invocation
2. Document query → SearchDocumentsTool → verified answer with citations
3. Calculation query → CalculateTool → verified answer from sandbox execution
4. Search + Calculate chain → multi-step tool execution in sequence
5. Vision query → AnalyzeImageTool with gemma3:4b configuration
6. Multi-turn memory → conversational state and cross-turn reference resolution
7. Max iterations safety → iteration limit enforcement and graceful fallback
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from agents.ollama_agent_provider import (
    OllamaAgentProvider,
    OllamaChatResponse,
    OllamaToolCall,
)
from agents.orchestrator import AgentOrchestrator, AgentResult
from agents.tool_executor import ToolExecutor
from agents.tool_registry import ToolRegistry
from agents.tools.analyze_image import AnalyzeImageTool
from agents.tools.calculate import CalculateTool
from agents.tools.search_documents import SearchDocumentsTool
from agents.tools.search_graph import SearchKnowledgeGraphTool
from calculation.service import CalculationService
from calculation.subprocess_sandbox import SubprocessSandboxProvider
from calculation.validator import CodeValidator
from database.chat_repository import ChatMessage
from generation.vision_provider import VisionProvider, VisionResult
from graph.query_service import GraphQueryService
from retrieval.retrieval_models import RetrievedChunk
from retrieval.service import RetrievalService


# ---------------------------------------------------------------------------
# In-Memory Test Fixtures & Fakes
# ---------------------------------------------------------------------------

class FakeChatRepository:
    """In-memory ChatRepository fake for multi-turn testing."""

    def __init__(self, messages: list[ChatMessage] | None = None) -> None:
        self.messages: list[ChatMessage] = messages or []
        self.get_recent_calls: list[tuple[str, int, str | None]] = []

    def get_recent_messages(
        self,
        session_id: str,
        limit: int,
        exclude_message_id: str | None = None,
    ) -> list[ChatMessage]:
        self.get_recent_calls.append((session_id, limit, exclude_message_id))
        matching = [
            m for m in self.messages
            if m.session_id == session_id and m.message_id != exclude_message_id
        ]
        return matching[-limit:]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> str:
        msg_id = f"msg-{len(self.messages) + 1}"
        msg = ChatMessage(
            message_id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            citations=citations or [],
            created_at=datetime.now(timezone.utc),
        )
        self.messages.append(msg)
        return msg_id


# ---------------------------------------------------------------------------
# Test Suite: Agent End-to-End Validation
# ---------------------------------------------------------------------------

class TestAgentEndToEnd(unittest.TestCase):
    """Full end-to-end test suite for the complete agentic pipeline."""

    def setUp(self):
        # 1. Setup Retrieval mock
        self.mock_retrieval = MagicMock(spec=RetrievalService)
        self.doc_tool = SearchDocumentsTool(self.mock_retrieval)

        # 2. Setup Graph mock
        self.mock_graph = MagicMock(spec=GraphQueryService)
        self.graph_tool = SearchKnowledgeGraphTool(self.mock_graph)

        # 3. Setup real CalculationService + Subprocess Sandbox
        self.calc_service = CalculationService(
            sandbox=SubprocessSandboxProvider(),
            validator=CodeValidator(),
            timeout_seconds=5.0,
            model_name="llama3.2",
        )
        self.calc_tool = CalculateTool(self.calc_service)

        # 4. Setup Vision mock
        self.mock_vision = MagicMock(spec=VisionProvider)
        self.mock_vision._model = "gemma3:4b"
        self.vision_tool = AnalyzeImageTool(self.mock_vision)

        # 5. Populate registry with all tools
        self.registry = ToolRegistry()
        self.registry.register(self.doc_tool)
        self.registry.register(self.graph_tool)
        self.registry.register(self.calc_tool)
        self.registry.register(self.vision_tool)

        self.executor = ToolExecutor(self.registry)
        self.events: list[dict[str, Any]] = []

    def _event_listener(self, stage: str, data: dict[str, Any]) -> None:
        self.events.append({"stage": stage, **data})

    def _create_orchestrator(
        self,
        mock_llm: OllamaAgentProvider,
        max_iterations: int = 8,
        chat_repository: Any | None = None,
    ) -> AgentOrchestrator:
        return AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=self.registry,
            tool_executor=self.executor,
            max_iterations=max_iterations,
            timeout_seconds=30.0,
            on_event=self._event_listener,
            chat_repository=chat_repository,
        )

    # -----------------------------------------------------------------------
    # Scenario 1: No-tool query ("Hello") → direct answer
    # -----------------------------------------------------------------------
    def test_e2e_no_tool_direct_answer(self):
        """Scenario 1: Non-technical conversational query answered without tools."""
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.return_value = OllamaChatResponse(
            content="Hello! I am OmniOps, your sovereign industrial intelligence workbench. How can I assist you today?",
            tool_calls=[],
        )

        orchestrator = self._create_orchestrator(mock_llm)
        result: AgentResult = orchestrator.run("Hello, who are you?")

        self.assertEqual(result.iterations, 1)
        self.assertEqual(len(result.tool_calls_made), 0)
        self.assertEqual(len(result.citations), 0)
        self.assertIsNone(result.error)
        self.assertIn("OmniOps", result.answer)

        # Verify event sequence
        stages = [e["stage"] for e in self.events]
        self.assertEqual(stages, ["AGENT_STARTED", "REASONING", "GENERATING_RESPONSE", "FINAL_ANSWER", "AGENT_COMPLETED"])

    # -----------------------------------------------------------------------
    # Scenario 2: Document query → SearchDocuments → answer
    # -----------------------------------------------------------------------
    def test_e2e_document_query_search_documents(self):
        """Scenario 2: Technical question retrieves SOP chunks and cites sources."""
        self.mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="chunk-c101-sop",
                document_id="SOP-C101-Crude-Tower.pdf",
                text="Distillation column C-101 operates at top pressure 1.8 bar gauge, top temperature 360 C.",
                score=0.96,
                page_index=8,
                section="Operating Conditions",
                metadata={"unit": "200", "equipment": "C-101"},
            )
        ]

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="I need to check the operating procedures for Column C-101.",
                tool_calls=[
                    OllamaToolCall(
                        name="search_documents",
                        arguments={"query": "Column C-101 operating pressure top temperature"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="According to SOP-C101-Crude-Tower.pdf (Page 8), Distillation column C-101 operates at 1.8 bar gauge and 360 °C.",
            ),
        ]

        orchestrator = self._create_orchestrator(mock_llm)
        result: AgentResult = orchestrator.run("What is the operating pressure and temperature of Crude Tower C-101?")

        self.assertEqual(result.iterations, 2)
        self.assertEqual(len(result.tool_calls_made), 1)
        self.assertEqual(result.tool_calls_made[0]["tool"], "search_documents")
        self.assertIn("1.8 bar", result.answer)
        self.assertIn("360 °C", result.answer)

        # Verify citation extraction
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0]["document_id"], "SOP-C101-Crude-Tower.pdf")
        self.assertEqual(result.citations[0]["chunk_id"], "chunk-c101-sop")
        self.assertEqual(result.citations[0]["page_index"], 8)

        # Verify SSE event compatibility
        stages = [e["stage"] for e in self.events]
        self.assertIn("SEARCHING_VECTOR_DB", stages)
        self.assertIn("TOOL_COMPLETED", stages)
        self.assertIn("AGENT_COMPLETED", stages)

    # -----------------------------------------------------------------------
    # Scenario 3: Calculation query → Calculate → answer
    # -----------------------------------------------------------------------
    def test_e2e_calculation_query_calculate(self):
        """Scenario 3: Numerical calculation executed in isolated sandbox."""
        # Calculate pressure drop: delta_P = 0.02 * (100 / 0.1) * (900 * 2**2 / 2) = 36000.0 Pa
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="I will calculate the pressure drop across the 100m pipeline using the Darcy-Weisbach equation.",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": "0.02 * (100 / 0.1) * (900 * 2**2 / 2)"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="The calculated pressure drop across the pipeline is 36,000 Pa (0.36 bar).",
            ),
        ]

        orchestrator = self._create_orchestrator(mock_llm)
        result: AgentResult = orchestrator.run(
            "Calculate pressure drop for L=100m, D=0.1m, f=0.02, density=900, velocity=2 m/s."
        )

        self.assertEqual(result.iterations, 2)
        self.assertEqual(len(result.tool_calls_made), 1)
        self.assertEqual(result.tool_calls_made[0]["tool"], "calculate")
        self.assertIn("36,000 Pa", result.answer)

    # -----------------------------------------------------------------------
    # Scenario 4: Search + Calculate chain
    # -----------------------------------------------------------------------
    def test_e2e_search_and_calculate_chain(self):
        """Scenario 4: Multi-step reasoning: Search document, then Calculate hydrostatic head."""
        self.mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="chunk-tk200",
                document_id="tank_farm_datasheets.pdf",
                text="Tank TK-200 design rating: design pressure = 2.5 bar (250,000 Pa), density = 1000 kg/m3.",
                score=0.93,
                page_index=15,
                section="Datasheet TK-200",
                metadata={"equipment": "TK-200"},
            )
        ]

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            # Step 1: Search document for Tank TK-200 specs
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="search_documents",
                        arguments={"query": "Tank TK-200 design pressure rating"},
                    )
                ],
            ),
            # Step 2: Calculate head: 250000 / (1000 * 9.81) = 25.484 m
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": "250000.0 / (1000.0 * 9.81)"},
                    )
                ],
            ),
            # Step 3: Synthesis
            OllamaChatResponse(
                content="From tank_farm_datasheets.pdf, Tank TK-200 design pressure is 2.5 bar. The equivalent water head is approximately 25.48 meters.",
            ),
        ]

        orchestrator = self._create_orchestrator(mock_llm)
        result: AgentResult = orchestrator.run(
            "Find the design pressure of Tank TK-200 and calculate the equivalent hydrostatic water head."
        )

        self.assertEqual(result.iterations, 3)
        self.assertEqual(len(result.tool_calls_made), 2)
        self.assertEqual(result.tool_calls_made[0]["tool"], "search_documents")
        self.assertEqual(result.tool_calls_made[1]["tool"], "calculate")
        self.assertIn("2.5 bar", result.answer)
        self.assertIn("25.48 meters", result.answer)
        self.assertEqual(len(result.citations), 1)

    # -----------------------------------------------------------------------
    # Scenario 5: Vision query (AnalyzeImage with gemma3:4b configuration)
    # -----------------------------------------------------------------------
    def test_e2e_vision_query_analyze_image(self):
        """Scenario 5: Image analysis tool invokes vision provider and synthesizes response."""
        # Create temporary dummy image file
        temp_img = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_img.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummypid")
        temp_img.close()

        try:
            self.mock_vision.describe_image.return_value = VisionResult(
                text="The diagram shows safety relief valves PSV-101 (set pressure 15.0 bar) and PSV-102 (set pressure 22.5 bar).",
                model="gemma3:4b",
                total_duration_ns=1_200_000_000,
                eval_count=35,
            )

            mock_llm = MagicMock(spec=OllamaAgentProvider)
            mock_llm.chat.side_effect = [
                OllamaChatResponse(
                    content="",
                    tool_calls=[
                        OllamaToolCall(
                            name="analyze_image",
                            arguments={
                                "image_path": temp_img.name,
                                "prompt": "Identify safety relief valves and their set pressures",
                            },
                        )
                    ],
                ),
                OllamaChatResponse(
                    content="The diagram contains two safety relief valves: PSV-101 (set pressure 15.0 bar) and PSV-102 (set pressure 22.5 bar).",
                ),
            ]

            orchestrator = self._create_orchestrator(mock_llm)
            result: AgentResult = orchestrator.run(
                f"Analyze this P&ID diagram at '{temp_img.name}' and identify safety relief valves."
            )

            self.assertEqual(result.iterations, 2)
            self.assertEqual(len(result.tool_calls_made), 1)
            self.assertEqual(result.tool_calls_made[0]["tool"], "analyze_image")
            self.assertIn("PSV-101", result.answer)
            self.assertIn("PSV-102", result.answer)
            self.mock_vision.describe_image.assert_called_once()
        finally:
            if os.path.exists(temp_img.name):
                os.remove(temp_img.name)

    # -----------------------------------------------------------------------
    # Scenario 6: Multi-turn memory
    # -----------------------------------------------------------------------
    def test_e2e_multi_turn_memory(self):
        """Scenario 6: Cross-turn resolution using ChatRepository session history."""
        # Setup conversation history in fake repository
        chat_repo = FakeChatRepository([
            ChatMessage(
                message_id="msg-turn1-u",
                session_id="session-boiler",
                role="user",
                content="What is the tag of the boiler feed water pump?",
                citations=[],
                created_at=datetime.now(timezone.utc),
            ),
            ChatMessage(
                message_id="msg-turn1-a",
                session_id="session-boiler",
                role="assistant",
                content="The boiler feed water pump is designated as BFW-P-101.",
                citations=[],
                created_at=datetime.now(timezone.utc),
            ),
        ])

        # Turn 2 user query: "What is its rated motor power?"
        current_msg_id = chat_repo.add_message(
            session_id="session-boiler",
            role="user",
            content="What is its rated motor power?",
        )

        self.mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="chunk-bfw101",
                document_id="electrical_drive_specs.pdf",
                text="Pump BFW-P-101 electric motor specification: rated power = 150 kW, voltage = 415 V.",
                score=0.95,
                page_index=4,
                section="Motors",
                metadata={"equipment": "BFW-P-101"},
            )
        ]

        captured_messages: list[list[dict[str, Any]]] = []

        def recording_chat(messages, tools=None):
            captured_messages.append(list(messages))
            if len(captured_messages) == 1:
                return OllamaChatResponse(
                    content="",
                    tool_calls=[
                        OllamaToolCall(
                            name="search_documents",
                            arguments={"query": "BFW-P-101 rated motor power specification"},
                        )
                    ],
                )
            return OllamaChatResponse(
                content="The rated motor power for boiler feed water pump BFW-P-101 is 150 kW.",
            )

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = recording_chat

        orchestrator = self._create_orchestrator(mock_llm, chat_repository=chat_repo)
        result: AgentResult = orchestrator.run(
            query="What is its rated motor power?",
            conversation_id="session-boiler",
            exclude_message_id=current_msg_id,
        )

        self.assertEqual(result.iterations, 2)
        self.assertIn("150 kW", result.answer)
        self.assertEqual(len(result.citations), 1)

        # Verify that Turn 1 messages were prepended to context
        first_call_msgs = captured_messages[0]
        self.assertEqual(first_call_msgs[0]["role"], "system")
        self.assertEqual(first_call_msgs[1]["content"], "What is the tag of the boiler feed water pump?")
        self.assertEqual(first_call_msgs[2]["content"], "The boiler feed water pump is designated as BFW-P-101.")
        self.assertEqual(first_call_msgs[3]["content"], "What is its rated motor power?")

    # -----------------------------------------------------------------------
    # Scenario 7: Max iterations safety
    # -----------------------------------------------------------------------
    def test_e2e_max_iterations_safety(self):
        """Scenario 7: Agent loop safely halts and falls back when max iterations reached."""
        # Simulate an infinite loop: LLM keeps calling calculate
        infinite_tool_calls = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": f"100 + {i}"},
                    )
                ],
            )
            for i in range(10)
        ]

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = infinite_tool_calls

        # Configure with max_iterations=3
        orchestrator = self._create_orchestrator(mock_llm, max_iterations=3)
        result: AgentResult = orchestrator.run("Perform iterative calculations indefinitely.")

        # Must halt at exactly max_iterations=3
        self.assertEqual(result.iterations, 3)
        self.assertEqual(len(result.tool_calls_made), 3)

        # Fallback answer should be provided
        self.assertIn("maximum processing limit", result.answer.lower())

        # Verify AGENT_MAX_ITERATIONS event emitted
        stages = [e["stage"] for e in self.events]
        self.assertIn("AGENT_MAX_ITERATIONS", stages)
        self.assertIn("AGENT_COMPLETED", stages)


if __name__ == "__main__":
    unittest.main()
