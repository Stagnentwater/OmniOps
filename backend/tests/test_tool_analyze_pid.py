"""Unit tests for the AnalyzePID tool."""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from agents.orchestrator import AgentOrchestrator
from agents.ollama_agent_provider import OllamaChatResponse, OllamaToolCall
from agents.tool_executor import ToolExecutor
from agents.tool_registry import ToolRegistry
from agents.tools.analyze_pid import AnalyzePIDResult, AnalyzePIDTool
from generation.vision_provider import VisionProvider, VisionResult


def _run_async(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


class TestAnalyzePIDDefinition(unittest.TestCase):
    """Tests for AnalyzePID tool definition and schema export."""

    def setUp(self):
        mock_provider = MagicMock(spec=VisionProvider)
        self.tool = AnalyzePIDTool(mock_provider)

    def test_definition_properties(self):
        defn = self.tool.definition
        self.assertEqual(defn.name, "analyze_pid")
        self.assertTrue(len(defn.description) > 30)
        self.assertIn("image_path", defn.parameters["properties"])
        self.assertIn("image_base64", defn.parameters["properties"])
        self.assertIn("focus_equipment", defn.parameters["properties"])

    def test_ollama_schema_format(self):
        schema = self.tool.definition.to_ollama_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "analyze_pid")
        self.assertIn("parameters", schema["function"])


class TestAnalyzePIDExecution(unittest.TestCase):
    """Tests for AnalyzePID execution and structured parsing."""

    def setUp(self):
        self.mock_provider = MagicMock(spec=VisionProvider)
        self.mock_provider._model = "gemma3:4b"
        self.tool = AnalyzePIDTool(self.mock_provider)

        # Temporary dummy image file
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.temp_file.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRpid_dummy")
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_missing_image(self):
        result = _run_async(self.tool.execute({}))
        self.assertFalse(result.success)
        self.assertIn("image_path", result.error)

    def test_invalid_argument_type(self):
        result = _run_async(self.tool.execute("not a dict"))  # type: ignore
        self.assertFalse(result.success)
        self.assertIn("dictionary", result.error)

    def test_nonexistent_image_file(self):
        result = _run_async(self.tool.execute({"image_path": "nonexistent/pid.png"}))
        self.assertFalse(result.success)
        self.assertIn("file not found", result.error)

    def test_successful_pid_parsing(self):
        pid_text = (
            "Equipment detected:\n"
            "- Pump P-101 (centrifugal crude feed pump)\n"
            "- Vessel V-200 (flash drum)\n"
            "- Heat Exchanger E-101\n"
            "Instrumentation:\n"
            "- Pressure Transmitter PT-101 on pump discharge\n"
            "- Temperature Transmitter TT-102\n"
            "Connections:\n"
            "- P-101 discharges to V-200 through line 4-HC-101\n"
            "- V-200 connects to E-101 inlet nozzle\n"
        )
        self.mock_provider.describe_image.return_value = VisionResult(
            text=pid_text,
            model="gemma3:4b",
            total_duration_ns=1_200_000_000,
            eval_count=65,
        )

        result = _run_async(self.tool.execute({"image_path": self.temp_file.name}))

        self.assertTrue(result.success)
        self.assertIsInstance(result.result, AnalyzePIDResult)
        
        # Verify structured extraction
        self.assertIn("P-101", result.result.equipment)
        self.assertIn("V-200", result.result.equipment)
        self.assertIn("E-101", result.result.equipment)
        self.assertIn("PT-101", result.result.instruments)
        self.assertIn("TT-102", result.result.instruments)
        self.assertTrue(len(result.result.connections) >= 2)
        self.assertEqual(result.result.confidence, 0.85)
        self.assertEqual(result.result.model, "gemma3:4b")

        # Verify formatted string
        self.assertIn("Identified Equipment", str(result.result))
        self.assertIn("P-101", str(result.result))
        self.assertIn("PT-101", str(result.result))

    def test_focus_equipment_prompt(self):
        self.mock_provider.describe_image.return_value = VisionResult(
            text="Exchanger E-105 details:\n- Inlets: Line 2-ST-10\n- Outlets: Line 2-CD-20",
            model="gemma3:4b",
            total_duration_ns=900_000_000,
            eval_count=45,
        )

        _run_async(self.tool.execute({
            "image_path": self.temp_file.name,
            "focus_equipment": "E-105",
        }))

        self.mock_provider.describe_image.assert_called_once()
        sent_prompt = self.mock_provider.describe_image.call_args[1]["prompt"]
        self.assertIn("E-105", sent_prompt)
        self.assertIn("SPECIAL FOCUS", sent_prompt)

    def test_model_not_installed_error_handling(self):
        self.mock_provider.describe_image.side_effect = RuntimeError(
            "model 'gemma3:4b' not found in Ollama"
        )

        result = _run_async(self.tool.execute({"image_path": self.temp_file.name}))

        self.assertFalse(result.success)
        self.assertIn("gemma3:4b", result.error)
        self.assertIn("ollama pull", result.error)


class TestAnalyzePIDIntegration(unittest.TestCase):
    """Tests for AnalyzePID tool with Registry, Executor, and Orchestrator."""

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.temp_file.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRpid_test")
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_registry_and_executor(self):
        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider.describe_image.return_value = VisionResult(
            text="P&ID shows Tank TK-301 connected to Pump P-301.",
            model="gemma3:4b",
            total_duration_ns=700_000_000,
            eval_count=30,
        )
        tool = AnalyzePIDTool(mock_provider)
        registry = ToolRegistry()
        registry.register(tool)

        self.assertIn("analyze_pid", registry)
        executor = ToolExecutor(registry)

        tool_result = _run_async(executor.execute("analyze_pid", {"image_path": self.temp_file.name}))

        self.assertTrue(tool_result.success)
        self.assertIn("TK-301", str(tool_result.result))

    def test_orchestrator_loop_with_pid_tool(self):
        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider.describe_image.return_value = VisionResult(
            text="P&ID reveals Pump P-101 discharge connects to Filter F-102.",
            model="gemma3:4b",
            total_duration_ns=800_000_000,
            eval_count=35,
        )
        tool = AnalyzePIDTool(mock_provider)
        registry = ToolRegistry()
        registry.register(tool)
        executor = ToolExecutor(registry)

        mock_llm = MagicMock()
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="analyze_pid",
                        arguments={"image_path": self.temp_file.name, "focus_equipment": "P-101"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="According to the P&ID diagram, Pump P-101 discharges to Filter F-102.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_iterations=5,
        )

        agent_result = orchestrator.run("Where does P-101 discharge to on the P&ID?")

        self.assertIsNotNone(agent_result.answer)
        self.assertIn("Filter F-102", agent_result.answer)
        self.assertEqual(agent_result.iterations, 2)
        self.assertEqual(len(agent_result.tool_calls_made), 1)
        self.assertEqual(agent_result.tool_calls_made[0]["tool"], "analyze_pid")


if __name__ == "__main__":
    unittest.main()
