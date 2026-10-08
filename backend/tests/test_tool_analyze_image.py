"""Unit tests for the AnalyzeImage tool."""

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
from agents.tools.analyze_image import AnalyzeImageResult, AnalyzeImageTool
from generation.vision_provider import VisionProvider, VisionResult


def _run_async(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.run(coro)


class TestAnalyzeImageDefinition(unittest.TestCase):
    """Tests for AnalyzeImage tool definition and schema export."""

    def setUp(self):
        mock_provider = MagicMock(spec=VisionProvider)
        self.tool = AnalyzeImageTool(mock_provider)

    def test_definition_properties(self):
        defn = self.tool.definition
        self.assertEqual(defn.name, "analyze_image")
        self.assertTrue(len(defn.description) > 30)
        self.assertIn("image_path", defn.parameters["properties"])
        self.assertIn("image_base64", defn.parameters["properties"])
        self.assertIn("prompt", defn.parameters["properties"])
        self.assertIn("task", defn.parameters["properties"])

    def test_ollama_schema_format(self):
        schema = self.tool.definition.to_ollama_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "analyze_image")
        self.assertIn("parameters", schema["function"])


class TestAnalyzeImageExecution(unittest.TestCase):
    """Tests for AnalyzeImage execution and error handling."""

    def setUp(self):
        self.mock_provider = MagicMock(spec=VisionProvider)
        self.mock_provider._model = "gemma3:4b"
        self.tool = AnalyzeImageTool(self.mock_provider)

        # Create temporary dummy image file
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.temp_file.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummycontent")
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_missing_image_path_and_base64(self):
        result = _run_async(self.tool.execute({}))
        self.assertFalse(result.success)
        self.assertIn("image_path", result.error)

    def test_invalid_argument_type(self):
        result = _run_async(self.tool.execute("not a dict"))  # type: ignore
        self.assertFalse(result.success)
        self.assertIn("dictionary", result.error)

    def test_nonexistent_image_path(self):
        result = _run_async(self.tool.execute({"image_path": "nonexistent/diagram.png"}))
        self.assertFalse(result.success)
        self.assertIn("Image file not found", result.error)

    def test_invalid_base64_data(self):
        result = _run_async(self.tool.execute({"image_base64": "!!!not_valid_base64!!!"}))
        self.assertFalse(result.success)
        self.assertIn("Invalid base64", result.error)

    def test_describe_image_via_file_path(self):
        self.mock_provider.describe_image.return_value = VisionResult(
            text="Centrifugal pump P-101 with pressure gauge reading 45 psi.",
            model="gemma3:4b",
            total_duration_ns=1_000_000_000,
            eval_count=42,
        )

        result = _run_async(self.tool.execute({
            "image_path": self.temp_file.name,
            "prompt": "What equipment is shown?",
        }))

        self.assertTrue(result.success)
        self.mock_provider.describe_image.assert_called_once()
        call_kwargs = self.mock_provider.describe_image.call_args[1]
        self.assertEqual(call_kwargs["prompt"], "What equipment is shown?")

        self.assertIsInstance(result.result, AnalyzeImageResult)
        self.assertIn("Centrifugal pump P-101", str(result.result))
        self.assertIn("gemma3:4b", str(result.result))
        self.assertEqual(result.result.model, "gemma3:4b")

    def test_describe_image_via_base64(self):
        dummy_bytes = b"\x89PNG\r\n\x1a\n"
        b64_str = base64.b64encode(dummy_bytes).decode("utf-8")

        self.mock_provider.describe_image.return_value = VisionResult(
            text="Storage tank TK-201 with high level alarm indicator.",
            model="gemma3:4b",
            total_duration_ns=800_000_000,
            eval_count=35,
        )

        result = _run_async(self.tool.execute({"image_base64": b64_str}))

        self.assertTrue(result.success)
        self.assertIn("TK-201", str(result.result))

    def test_classify_image_task(self):
        self.mock_provider.classify_image.return_value = "PID"

        result = _run_async(self.tool.execute({
            "image_path": self.temp_file.name,
            "task": "classify",
        }))

        self.assertTrue(result.success)
        self.mock_provider.classify_image.assert_called_once()
        self.assertIn("PID", str(result.result))

    def test_model_not_installed_or_communication_failure(self):
        self.mock_provider.describe_image.side_effect = RuntimeError(
            "model 'gemma3:4b' not found, try pulling it first"
        )

        result = _run_async(self.tool.execute({"image_path": self.temp_file.name}))

        self.assertFalse(result.success)
        self.assertIn("gemma3:4b", result.error)
        self.assertIn("ollama pull", result.error)


class TestAnalyzeImageIntegration(unittest.TestCase):
    """Tests for AnalyzeImage tool with Registry, Executor, and Orchestrator."""

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.temp_file.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest")
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_registry_and_executor(self):
        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider.describe_image.return_value = VisionResult(
            text="Motor M-501 nameplate: 15 kW, 400 V, 50 Hz.",
            model="gemma3:4b",
            total_duration_ns=500_000_000,
            eval_count=20,
        )
        tool = AnalyzeImageTool(mock_provider)
        registry = ToolRegistry()
        registry.register(tool)

        self.assertIn("analyze_image", registry)
        executor = ToolExecutor(registry)

        tool_result = _run_async(executor.execute("analyze_image", {"image_path": self.temp_file.name}))

        self.assertTrue(tool_result.success)
        self.assertIn("Motor M-501", str(tool_result.result))

    def test_orchestrator_loop_with_vision_tool(self):
        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider.describe_image.return_value = VisionResult(
            text="Gate valve V-105 is currently in the CLOSED position.",
            model="gemma3:4b",
            total_duration_ns=600_000_000,
            eval_count=25,
        )
        tool = AnalyzeImageTool(mock_provider)
        registry = ToolRegistry()
        registry.register(tool)
        executor = ToolExecutor(registry)

        # Mock LLM calling analyze_image tool
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="analyze_image",
                        arguments={"image_path": self.temp_file.name, "prompt": "Is the valve open or closed?"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="Based on the image analysis, valve V-105 is CLOSED.",
            ),
        ]

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_iterations=5,
        )

        agent_result = orchestrator.run("Can you check the valve status in this picture?")

        self.assertIsNotNone(agent_result.answer)
        self.assertIn("CLOSED", agent_result.answer)
        self.assertEqual(agent_result.iterations, 2)
        self.assertEqual(len(agent_result.tool_calls_made), 1)
        self.assertEqual(agent_result.tool_calls_made[0]["tool"], "analyze_image")


if __name__ == "__main__":
    unittest.main()
