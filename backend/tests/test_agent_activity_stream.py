"""Unit and integration tests for Agent Activity Stream and Live Tool/Code Visibility."""

import unittest
from unittest.mock import MagicMock, patch
import time

from agents.orchestrator import AgentOrchestrator, AgentResult
from agents.ollama_agent_provider import OllamaAgentProvider, OllamaChatResponse, OllamaToolCall
from agents.tool_registry import ToolRegistry
from agents.tool_executor import ToolExecutor
from agents.tool_interface import Tool, ToolDefinition, ToolResult
from agents.tools.calculate import CalculateToolResult
from agents.tools.search_documents import SearchDocumentsResult
from agents.tools.search_graph import SearchGraphResult
from retrieval.retrieval_models import RetrievedChunk


class DummySearchTool(Tool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_documents",
            description="Search documents",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        )

    async def execute(self, arguments: dict) -> ToolResult:
        chunks = [
            RetrievedChunk(
                chunk_id="chk-1",
                document_id="doc-1.pdf",
                text="Operating pressure is 15 bar.",
                score=0.92,
                page_index=1,
                section="Conditions",
                metadata={},
            ),
            RetrievedChunk(
                chunk_id="chk-2",
                document_id="doc-2.pdf",
                text="Operating temperature is 250 C.",
                score=0.88,
                page_index=3,
                section="Conditions",
                metadata={},
            ),
        ]
        return ToolResult(
            tool_name="search_documents",
            success=True,
            result=SearchDocumentsResult("Found 2 chunks", chunks),
            execution_time_ms=45.0,
        )


class DummyCalculateTool(Tool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calculate",
            description="Run calculation",
            parameters={"type": "object", "properties": {"code": {"type": "string"}}},
        )

    async def execute(self, arguments: dict) -> ToolResult:
        code = arguments.get("code", "")
        if "fail" in code:
            return ToolResult(
                tool_name="calculate",
                success=False,
                result=None,
                error="ZeroDivisionError: division by zero",
                execution_time_ms=12.0,
            )
        return ToolResult(
            tool_name="calculate",
            success=True,
            result=CalculateToolResult("Result: 42.0", raw_result="42.0", exit_code=0, execution_time_ms=15.0),
            execution_time_ms=15.0,
        )


class TestAgentActivityStream(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(DummySearchTool())
        self.registry.register(DummyCalculateTool())
        self.executor = ToolExecutor(self.registry)
        self.events = []

    def _event_handler(self, stage: str, data: dict):
        self.events.append(data)

    def test_activity_events_search_and_calculate(self):
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            # Iteration 1: Call search_documents
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(name="search_documents", arguments={"query": "pump pressure"})
                ],
            ),
            # Iteration 2: Call calculate
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(name="calculate", arguments={"code": "result = 21 * 2"})
                ],
            ),
            # Iteration 3: Final answer
            OllamaChatResponse(
                content="The operating pressure is 42.0 bar.",
                tool_calls=[],
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=self.registry,
            tool_executor=self.executor,
            on_event=self._event_handler,
        )

        res = orchestrator.run("What is the pump pressure?")
        self.assertIn("42.0 bar", res.answer)

        # Verify event stream items
        event_types = [e.get("type") for e in self.events if "type" in e]
        self.assertIn("agent_started", event_types)
        self.assertIn("reasoning_summary", event_types)
        self.assertIn("tool_started", event_types)
        self.assertIn("tool_completed", event_types)
        self.assertIn("code_generated", event_types)
        self.assertIn("code_execution_started", event_types)
        self.assertIn("code_execution_completed", event_types)
        self.assertIn("final_answer_started", event_types)
        self.assertIn("agent_completed", event_types)

        # Verify activities accumulated in result
        self.assertGreater(len(res.activities), 0)
        calc_events = [a for a in res.activities if a.get("tool") == "calculate"]
        self.assertTrue(any("code" in a.get("metadata", {}) for a in calc_events))

    def test_activity_events_tool_failure(self):
        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = [
            # Iteration 1: Call calculate with failing code
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(name="calculate", arguments={"code": "fail = 1 / 0"})
                ],
            ),
            # Iteration 2: Final answer after error
            OllamaChatResponse(
                content="Calculation failed due to zero division.",
                tool_calls=[],
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=self.registry,
            tool_executor=self.executor,
            on_event=self._event_handler,
        )

        res = orchestrator.run("Calculate fail")
        failed_events = [e for e in self.events if e.get("type") == "tool_failed"]
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(failed_events[0]["status"], "failed")
        self.assertIn("ZeroDivisionError", failed_events[0]["message"])


if __name__ == "__main__":
    unittest.main()
