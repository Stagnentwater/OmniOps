"""Unit tests for the Calculate tool."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from agents.orchestrator import AgentOrchestrator
from agents.ollama_agent_provider import OllamaChatResponse, OllamaToolCall
from agents.tool_executor import ToolExecutor
from agents.tool_registry import ToolRegistry
from agents.tools.calculate import CalculateTool, CalculateToolResult
from calculation.models import CalculationRequest, CalculationResult, create_audit
from calculation.service import CalculationService
from calculation.subprocess_sandbox import SubprocessSandboxProvider
from calculation.validator import CodeValidator


def _run_async(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


class TestCalculateDefinition(unittest.TestCase):
    """Tests for Calculate tool definition and schema export."""

    def setUp(self):
        mock_service = MagicMock(spec=CalculationService)
        self.tool = CalculateTool(mock_service)

    def test_definition_properties(self):
        defn = self.tool.definition
        self.assertEqual(defn.name, "calculate")
        self.assertTrue(len(defn.description) > 30)
        self.assertIn("code", defn.parameters["properties"])
        self.assertIn("expression", defn.parameters["properties"])
        self.assertIn("inputs", defn.parameters["properties"])

    def test_ollama_schema_format(self):
        schema = self.tool.definition.to_ollama_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "calculate")
        self.assertIn("parameters", schema["function"])


class TestCalculateExecution(unittest.TestCase):
    """Tests for Calculate execution with real CalculationService and sandbox."""

    def setUp(self):
        # Use real CalculationService with SubprocessSandboxProvider and CodeValidator
        self.service = CalculationService(
            sandbox=SubprocessSandboxProvider(),
            validator=CodeValidator(),
            timeout_seconds=5.0,
            model_name="llama3.2",
        )
        self.tool = CalculateTool(self.service)

    def test_missing_code_and_expression(self):
        result = _run_async(self.tool.execute({}))
        self.assertFalse(result.success)
        self.assertIn("code", result.error)

    def test_invalid_arguments_type(self):
        result = _run_async(self.tool.execute("not a dict"))  # type: ignore
        self.assertFalse(result.success)
        self.assertIn("dictionary", result.error)

    def test_direct_expression_calculation(self):
        # 50 * 4.184 * 25 = 5230.0
        result = _run_async(self.tool.execute({"expression": "50 * 4.184 * 25"}))

        self.assertTrue(result.success)
        self.assertIsInstance(result.result, CalculateToolResult)
        self.assertEqual(result.result.raw_result, "5230.0")
        self.assertIn("5230.0", str(result.result))
        self.assertEqual(result.result.exit_code, 0)
        self.assertIsNotNone(result.result.audit)

    def test_single_line_code_auto_wrapping(self):
        # LLM writes expression in code field without 'result ='
        result = _run_async(self.tool.execute({"code": "math.sqrt(144) * 5"}))

        self.assertTrue(result.success)
        self.assertEqual(result.result.raw_result, "60.0")
        self.assertIn("60.0", str(result.result))

    def test_full_python_code_with_inputs(self):
        code = (
            "import math\n"
            "area = math.pi * (radius ** 2)\n"
            "result = round(area * height, 2)\n"
        )
        inputs = {"radius": 3.0, "height": 10.0}

        result = _run_async(self.tool.execute({
            "code": code,
            "inputs": inputs,
            "query": "Cylinder volume calculation",
        }))

        self.assertTrue(result.success)
        # pi * 9 * 10 = 282.7433... -> 282.74
        self.assertEqual(result.result.raw_result, "282.74")
        self.assertIn("282.74", str(result.result))

    def test_security_blocked_import_rejected(self):
        # CodeValidator should reject import os
        result = _run_async(self.tool.execute({
            "code": "import os\nresult = os.listdir('.')",
        }))

        self.assertFalse(result.success)
        self.assertIn("Code validation failed", result.error)
        self.assertIn("os", result.error)

    def test_security_blocked_builtin_rejected(self):
        # CodeValidator should reject open
        result = _run_async(self.tool.execute({
            "code": "f = open('/etc/passwd')\nresult = f.read()",
        }))

        self.assertFalse(result.success)
        self.assertIn("Code validation failed", result.error)

    def test_runtime_zero_division_error(self):
        result = _run_async(self.tool.execute({"expression": "100 / 0"}))

        self.assertFalse(result.success)
        self.assertIn("ZeroDivisionError", result.error)


class TestCalculateIntegration(unittest.TestCase):
    """Tests for Calculate tool through ToolRegistry, Executor, and Orchestrator."""

    def test_registry_and_executor(self):
        service = CalculationService(
            sandbox=SubprocessSandboxProvider(),
            validator=CodeValidator(),
        )
        tool = CalculateTool(service)
        registry = ToolRegistry()
        registry.register(tool)

        self.assertIn("calculate", registry)
        executor = ToolExecutor(registry)

        tool_result = _run_async(executor.execute("calculate", {"expression": "25 * 4"}))

        self.assertTrue(tool_result.success)
        self.assertIn("100", str(tool_result.result))

    def test_orchestrator_loop_with_calculate_tool(self):
        service = CalculationService(
            sandbox=SubprocessSandboxProvider(),
            validator=CodeValidator(),
        )
        tool = CalculateTool(service)
        registry = ToolRegistry()
        registry.register(tool)
        executor = ToolExecutor(registry)

        # Mock LLM calling calculate tool
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": "150 * 0.0689476"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="150 psi converts to approximately 10.34 bar.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_iterations=5,
        )

        agent_result = orchestrator.run("Convert 150 psi to bar.")

        self.assertIsNotNone(agent_result.answer)
        self.assertIn("10.34 bar", agent_result.answer)
        self.assertEqual(agent_result.iterations, 2)
        self.assertEqual(len(agent_result.tool_calls_made), 1)
        self.assertEqual(agent_result.tool_calls_made[0]["tool"], "calculate")


if __name__ == "__main__":
    unittest.main()
