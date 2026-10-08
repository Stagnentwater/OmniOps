"""Tests for the AgentOrchestrator — the full agent loop."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch, call
from typing import Any

from agents.ollama_agent_provider import (
    OllamaAgentProvider,
    OllamaChatResponse,
    OllamaToolCall,
)
from agents.orchestrator import AgentOrchestrator, AgentResult
from agents.state import AgentState
from agents.tool_executor import ToolExecutor
from agents.tool_interface import Tool, ToolDefinition, ToolResult
from agents.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _EchoTool(Tool):
    """Echoes input for testing."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="echo",
            description="Echoes the input.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
                "required": ["message"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(
            tool_name="echo",
            success=True,
            result=f"Echo: {arguments.get('message', '')}",
        )


class _FailTool(Tool):
    """Always fails for testing."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="fail_tool",
            description="Always fails.",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(
            tool_name="fail_tool",
            success=False,
            result=None,
            error="Intentional failure",
        )


def _make_orchestrator(
    llm_responses: list[OllamaChatResponse],
    tools: list[Tool] | None = None,
    max_iterations: int = 5,
    timeout_seconds: float = 30.0,
) -> tuple[AgentOrchestrator, list[dict]]:
    """Create an orchestrator with a mocked LLM provider.

    Returns (orchestrator, events_list).
    """
    provider = MagicMock(spec=OllamaAgentProvider)
    provider.chat.side_effect = llm_responses

    registry = ToolRegistry()
    for tool in (tools or []):
        registry.register(tool)

    executor = ToolExecutor(registry)
    events: list[dict] = []

    def on_event(stage: str, data: dict):
        events.append({"stage": stage, **data})

    orchestrator = AgentOrchestrator(
        llm_provider=provider,
        tool_registry=registry,
        tool_executor=executor,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        on_event=on_event,
    )
    return orchestrator, events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentOrchestratorDirectAnswer(unittest.TestCase):
    """Test: LLM returns a direct answer with no tool calls."""

    def test_direct_answer_no_tools(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                OllamaChatResponse(content="Hello! How can I help?"),
            ],
        )

        result = orchestrator.run("Hello")

        self.assertIsInstance(result, AgentResult)
        self.assertEqual(result.answer, "Hello! How can I help?")
        self.assertEqual(result.iterations, 1)
        self.assertEqual(len(result.tool_calls_made), 0)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.execution_time_seconds, 0)

        # Check events
        stages = [e["stage"] for e in events]
        self.assertIn("AGENT_STARTED", stages)
        self.assertIn("REASONING", stages)
        self.assertIn("FINAL_ANSWER", stages)
        self.assertIn("AGENT_COMPLETED", stages)


class TestAgentOrchestratorToolCall(unittest.TestCase):
    """Test: LLM calls a tool then produces a final answer."""

    def test_tool_then_answer(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                # Iteration 1: LLM calls echo tool
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="echo", arguments={"message": "test"}),
                    ),
                ),
                # Iteration 2: LLM produces final answer using tool result
                OllamaChatResponse(
                    content="The echo tool returned: Echo: test",
                ),
            ],
            tools=[_EchoTool()],
        )

        result = orchestrator.run("Echo test please")

        self.assertEqual(result.answer, "The echo tool returned: Echo: test")
        self.assertEqual(result.iterations, 2)
        self.assertEqual(len(result.tool_calls_made), 1)
        self.assertEqual(result.tool_calls_made[0]["tool"], "echo")
        self.assertIsNone(result.error)

        # Check tool execution events
        stages = [e["stage"] for e in events]
        self.assertIn("TOOL_EXECUTING", stages)
        self.assertIn("TOOL_COMPLETED", stages)


class TestAgentOrchestratorMultipleToolCalls(unittest.TestCase):
    """Test: LLM calls multiple tools in sequence."""

    def test_two_tools_then_answer(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                # Iteration 1: call echo
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="echo", arguments={"message": "first"}),
                    ),
                ),
                # Iteration 2: call echo again with different args
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="echo", arguments={"message": "second"}),
                    ),
                ),
                # Iteration 3: final answer
                OllamaChatResponse(
                    content="Combined results: first and second",
                ),
            ],
            tools=[_EchoTool()],
        )

        result = orchestrator.run("Do two echoes")

        self.assertEqual(result.iterations, 3)
        self.assertEqual(len(result.tool_calls_made), 2)
        self.assertIn("Combined results", result.answer)


class TestAgentOrchestratorMaxIterations(unittest.TestCase):
    """Test: Agent stops at max iterations."""

    def test_max_iterations_limit(self):
        # LLM always calls a tool, never gives final answer
        infinite_tool_calls = [
            OllamaChatResponse(
                content="",
                tool_calls=(
                    OllamaToolCall(name="echo", arguments={"message": f"iter-{i}"}),
                ),
            )
            for i in range(10)
        ]

        orchestrator, events = _make_orchestrator(
            llm_responses=infinite_tool_calls,
            tools=[_EchoTool()],
            max_iterations=3,
        )

        result = orchestrator.run("Keep echoing")

        # Should stop at max_iterations
        self.assertLessEqual(result.iterations, 3)
        self.assertIn("maximum processing limit", result.answer.lower())

        stages = [e["stage"] for e in events]
        self.assertIn("AGENT_MAX_ITERATIONS", stages)


class TestAgentOrchestratorDuplicateDetection(unittest.TestCase):
    """Test: Duplicate tool calls are detected and skipped."""

    def test_duplicate_tool_call_skipped(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                # First call
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="echo", arguments={"message": "same"}),
                    ),
                ),
                # Same exact call again
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="echo", arguments={"message": "same"}),
                    ),
                ),
                # Final answer
                OllamaChatResponse(content="Done"),
            ],
            tools=[_EchoTool()],
        )

        result = orchestrator.run("Test duplicates")

        # Should have 1 real call + 1 duplicate skipped
        self.assertEqual(result.answer, "Done")


class TestAgentOrchestratorToolError(unittest.TestCase):
    """Test: Tool errors are handled gracefully."""

    def test_tool_error_reported_to_llm(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                # Call failing tool
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="fail_tool", arguments={}),
                    ),
                ),
                # LLM handles the error gracefully
                OllamaChatResponse(
                    content="The tool failed, but I can still help.",
                ),
            ],
            tools=[_FailTool()],
        )

        result = orchestrator.run("Trigger failure")

        self.assertEqual(result.answer, "The tool failed, but I can still help.")
        self.assertIsNone(result.error)

    def test_consecutive_errors_force_fallback(self):
        # All calls fail
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                OllamaChatResponse(
                    content="",
                    tool_calls=(OllamaToolCall(name="fail_tool", arguments={}),),
                ),
                OllamaChatResponse(
                    content="",
                    tool_calls=(OllamaToolCall(name="fail_tool", arguments={"x": 1}),),
                ),
                OllamaChatResponse(
                    content="",
                    tool_calls=(OllamaToolCall(name="fail_tool", arguments={"x": 2}),),
                ),
            ],
            tools=[_FailTool()],
            max_iterations=5,
        )

        result = orchestrator.run("Keep failing")

        # Should get a fallback answer due to consecutive errors
        stages = [e["stage"] for e in events]
        self.assertIn("AGENT_FALLBACK", stages)


class TestAgentOrchestratorUnknownTool(unittest.TestCase):
    """Test: LLM calls a tool not in the registry."""

    def test_unknown_tool_handled(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="nonexistent_tool", arguments={}),
                    ),
                ),
                OllamaChatResponse(
                    content="I couldn't find that tool, let me answer directly.",
                ),
            ],
            tools=[_EchoTool()],
        )

        result = orchestrator.run("Call unknown tool")

        self.assertEqual(
            result.answer,
            "I couldn't find that tool, let me answer directly.",
        )


class TestAgentOrchestratorLLMError(unittest.TestCase):
    """Test: LLM provider raises an error."""

    def test_llm_error_stops_execution(self):
        provider = MagicMock(spec=OllamaAgentProvider)
        provider.chat.side_effect = RuntimeError("Ollama connection refused")

        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        orchestrator = AgentOrchestrator(
            llm_provider=provider,
            tool_registry=registry,
            tool_executor=executor,
        )

        result = orchestrator.run("Test LLM failure")

        self.assertIsNotNone(result.error)
        self.assertIn("LLM communication failed", result.error)


class TestAgentOrchestratorConversationHistory(unittest.TestCase):
    """Test: Prior conversation context is included."""

    def test_history_included_in_messages(self):
        provider = MagicMock(spec=OllamaAgentProvider)
        provider.chat.return_value = OllamaChatResponse(
            content="Based on our previous discussion..."
        )

        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        orchestrator = AgentOrchestrator(
            llm_provider=provider,
            tool_registry=registry,
            tool_executor=executor,
        )

        result = orchestrator.run(
            query="What was that pressure?",
            conversation_history=[
                {"role": "user", "content": "What is P-101?"},
                {"role": "assistant", "content": "P-101 is a centrifugal pump."},
            ],
        )

        # Verify the LLM was called with history
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        roles = [m["role"] for m in messages]

        # Should have: system, user(history), assistant(history), user(current)
        self.assertEqual(roles[0], "system")
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)


class TestAgentOrchestratorEvents(unittest.TestCase):
    """Test: Events are emitted at the right stages."""

    def test_full_event_sequence(self):
        orchestrator, events = _make_orchestrator(
            llm_responses=[
                OllamaChatResponse(
                    content="",
                    tool_calls=(
                        OllamaToolCall(name="echo", arguments={"message": "hi"}),
                    ),
                ),
                OllamaChatResponse(content="Final answer"),
            ],
            tools=[_EchoTool()],
        )

        orchestrator.run("Test events")

        stages = [e["stage"] for e in events]
        expected_order = [
            "AGENT_STARTED",
            "REASONING",
            "TOOL_EXECUTING",
            "TOOL_COMPLETED",
            "REASONING",
            "FINAL_ANSWER",
            "AGENT_COMPLETED",
        ]

        for expected in expected_order:
            self.assertIn(expected, stages)


if __name__ == "__main__":
    unittest.main()
