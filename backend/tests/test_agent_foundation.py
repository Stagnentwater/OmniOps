"""Unit tests for the agent foundation: Tool interface, Registry, Executor, State."""

from __future__ import annotations

import asyncio
import time
import unittest
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult
from agents.tool_registry import ToolRegistry
from agents.tool_executor import ToolExecutor
from agents.state import AgentState


# ---------------------------------------------------------------------------
# Test Tool Implementations
# ---------------------------------------------------------------------------

class EchoTool(Tool):
    """Test tool that echoes its input."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="echo",
            description="Echoes the input message back.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo"},
                },
                "required": ["message"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        message = arguments.get("message", "")
        return ToolResult(
            tool_name="echo",
            success=True,
            result=f"Echo: {message}",
        )


class FailingTool(Tool):
    """Test tool that always fails."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="failing_tool",
            description="A tool that always fails for testing.",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(
            tool_name="failing_tool",
            success=False,
            result=None,
            error="Intentional test failure",
        )


class ExceptionTool(Tool):
    """Test tool that raises an exception."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="exception_tool",
            description="A tool that raises an exception.",
            parameters={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        raise RuntimeError("Intentional exception for testing")


class AddTool(Tool):
    """Test tool that adds two numbers."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="add",
            description="Adds two numbers.",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"},
                },
                "required": ["a", "b"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        return ToolResult(
            tool_name="add",
            success=True,
            result=a + b,
        )


# ---------------------------------------------------------------------------
# ToolDefinition Tests
# ---------------------------------------------------------------------------

class TestToolDefinition(unittest.TestCase):
    """Tests for ToolDefinition data contract."""

    def test_frozen(self):
        td = ToolDefinition(name="test", description="desc", parameters={})
        with self.assertRaises(AttributeError):
            td.name = "modified"  # type: ignore[misc]

    def test_to_ollama_schema(self):
        td = ToolDefinition(
            name="search",
            description="Search docs",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        )
        schema = td.to_ollama_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "search")
        self.assertEqual(schema["function"]["description"], "Search docs")
        self.assertIn("query", schema["function"]["parameters"]["properties"])


# ---------------------------------------------------------------------------
# ToolResult Tests
# ---------------------------------------------------------------------------

class TestToolResult(unittest.TestCase):
    """Tests for ToolResult data contract."""

    def test_success_message(self):
        result = ToolResult(tool_name="t", success=True, result="hello")
        self.assertEqual(result.to_message_content(), "hello")

    def test_error_message(self):
        result = ToolResult(tool_name="t", success=False, result=None, error="bad")
        content = result.to_message_content()
        self.assertIn("failed", content)
        self.assertIn("bad", content)

    def test_frozen(self):
        result = ToolResult(tool_name="t", success=True, result="x")
        with self.assertRaises(AttributeError):
            result.success = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolRegistry Tests
# ---------------------------------------------------------------------------

class TestToolRegistry(unittest.TestCase):
    """Tests for the ToolRegistry."""

    def setUp(self):
        self.registry = ToolRegistry()
        self.echo = EchoTool()
        self.add = AddTool()

    def test_register_and_get(self):
        self.registry.register(self.echo)
        tool = self.registry.get("echo")
        self.assertIsInstance(tool, EchoTool)

    def test_register_duplicate_raises(self):
        self.registry.register(self.echo)
        with self.assertRaises(ValueError):
            self.registry.register(EchoTool())

    def test_get_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.registry.get("nonexistent")

    def test_unregister(self):
        self.registry.register(self.echo)
        self.registry.unregister("echo")
        self.assertNotIn("echo", self.registry)

    def test_unregister_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.registry.unregister("nonexistent")

    def test_list_tools(self):
        self.registry.register(self.echo)
        self.registry.register(self.add)
        names = self.registry.list_tools()
        self.assertIn("echo", names)
        self.assertIn("add", names)
        self.assertEqual(len(names), 2)

    def test_contains(self):
        self.registry.register(self.echo)
        self.assertIn("echo", self.registry)
        self.assertNotIn("unknown", self.registry)

    def test_len(self):
        self.assertEqual(len(self.registry), 0)
        self.registry.register(self.echo)
        self.assertEqual(len(self.registry), 1)

    def test_get_definitions(self):
        self.registry.register(self.echo)
        self.registry.register(self.add)
        defs = self.registry.get_definitions()
        self.assertEqual(len(defs), 2)
        self.assertIsInstance(defs[0], ToolDefinition)

    def test_get_ollama_schemas(self):
        self.registry.register(self.echo)
        schemas = self.registry.get_ollama_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["type"], "function")
        self.assertEqual(schemas[0]["function"]["name"], "echo")


# ---------------------------------------------------------------------------
# ToolExecutor Tests
# ---------------------------------------------------------------------------

class TestToolExecutor(unittest.TestCase):
    """Tests for the ToolExecutor."""

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        self.registry.register(ExceptionTool())
        self.registry.register(AddTool())
        self.executor = ToolExecutor(self.registry)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_execute_success(self):
        result = self._run(self.executor.execute("echo", {"message": "hello"}))
        self.assertTrue(result.success)
        self.assertEqual(result.result, "Echo: hello")
        self.assertGreaterEqual(result.execution_time_ms, 0)

    def test_execute_unknown_tool(self):
        result = self._run(self.executor.execute("nonexistent", {}))
        self.assertFalse(result.success)
        self.assertIn("Unknown tool", result.error)

    def test_execute_failing_tool(self):
        result = self._run(self.executor.execute("failing_tool", {}))
        self.assertFalse(result.success)
        self.assertIn("Intentional test failure", result.error)

    def test_execute_exception_tool(self):
        result = self._run(self.executor.execute("exception_tool", {}))
        self.assertFalse(result.success)
        self.assertIn("Intentional exception", result.error)

    def test_execute_add(self):
        result = self._run(self.executor.execute("add", {"a": 3, "b": 5}))
        self.assertTrue(result.success)
        self.assertEqual(result.result, 8)


# ---------------------------------------------------------------------------
# AgentState Tests
# ---------------------------------------------------------------------------

class TestAgentState(unittest.TestCase):
    """Tests for the AgentState."""

    def test_default_creation(self):
        state = AgentState()
        self.assertIsNotNone(state.execution_id)
        self.assertEqual(state.iteration_count, 0)
        self.assertEqual(state.max_iterations, 8)
        self.assertIsNone(state.final_answer)
        self.assertFalse(state.is_finished)

    def test_is_finished_with_final_answer(self):
        state = AgentState()
        state.final_answer = "Done"
        self.assertTrue(state.is_finished)

    def test_is_finished_with_error(self):
        state = AgentState()
        state.error = "Something broke"
        self.assertTrue(state.is_finished)

    def test_iteration_limit(self):
        state = AgentState(max_iterations=3)
        state.iteration_count = 3
        self.assertTrue(state.is_iteration_limit_reached)
        self.assertTrue(state.is_finished)

    def test_timeout(self):
        state = AgentState(timeout_seconds=0.01)
        time.sleep(0.02)
        self.assertTrue(state.is_timed_out)
        self.assertTrue(state.is_finished)

    def test_add_tool_call(self):
        state = AgentState()
        state.add_tool_call("search", {"query": "pump"})
        self.assertEqual(len(state.tool_calls), 1)
        self.assertEqual(state.tool_calls[0]["tool_name"], "search")

    def test_duplicate_detection(self):
        state = AgentState()
        state.add_tool_call("search", {"query": "pump"})
        self.assertTrue(state.has_duplicate_tool_call("search", {"query": "pump"}))
        self.assertFalse(state.has_duplicate_tool_call("search", {"query": "valve"}))
        self.assertFalse(state.has_duplicate_tool_call("graph", {"query": "pump"}))

    def test_consecutive_errors(self):
        state = AgentState()
        state.tool_results.append(ToolResult("a", True, "ok"))
        self.assertEqual(state.consecutive_errors, 0)

        state.tool_results.append(ToolResult("b", False, None, error="err1"))
        self.assertEqual(state.consecutive_errors, 1)

        state.tool_results.append(ToolResult("c", False, None, error="err2"))
        self.assertEqual(state.consecutive_errors, 2)

        state.tool_results.append(ToolResult("d", True, "ok"))
        self.assertEqual(state.consecutive_errors, 0)

    def test_elapsed_seconds(self):
        state = AgentState()
        time.sleep(0.05)
        self.assertGreater(state.elapsed_seconds, 0.04)


if __name__ == "__main__":
    unittest.main()
