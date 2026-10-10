"""Unit tests for chat query image processing and attachment handling."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import MagicMock, patch

from api.routes.query import QueryRequest, _process_attached_image


class TestImageChatQuery(unittest.TestCase):
    """Test image attachment decoding, storage, and metadata persistence."""

    def test_query_request_model_with_image(self) -> None:
        """Verify QueryRequest accepts image_base64 and image_filename."""
        req = QueryRequest(
            query="Inspect this pump",
            session_id="session-123",
            image_base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            image_filename="pump.png",
        )
        self.assertEqual(req.query, "Inspect this pump")
        self.assertEqual(req.image_filename, "pump.png")
        self.assertTrue(req.image_base64.startswith("data:image/png;base64,"))

    @patch("storage.factory.get_storage_service")
    @patch("database.repositories.MetadataRepository")
    def test_process_attached_image(self, mock_meta_repo_cls, mock_get_storage) -> None:
        """Verify _process_attached_image decodes, stores via StorageService, and returns metadata."""
        mock_storage = MagicMock()
        mock_stored = MagicMock()
        mock_stored.storage_key = "documents/test_id/sample.png"
        mock_storage.put_bytes.return_value = mock_stored
        mock_get_storage.return_value = mock_storage

        mock_meta_repo = MagicMock()
        mock_meta_repo_cls.return_value = mock_meta_repo

        # 1x1 transparent PNG base64
        fake_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        doc_id, local_path, storage_url = _process_attached_image(fake_b64, "sample.png")

        self.assertTrue(len(doc_id) > 10)
        self.assertEqual(storage_url, f"/documents/{doc_id}/content")
        self.assertTrue(local_path.endswith("sample.png"))

        mock_storage.put_bytes.assert_called_once()
        mock_meta_repo.save_document_metadata.assert_called_once()

    def test_agent_system_prompt_has_non_refinery_image_rule(self) -> None:
        """Verify _SYSTEM_PROMPT in orchestrator contains explicit rules for dummy/non-refinery images."""
        from agents.orchestrator import _SYSTEM_PROMPT
        self.assertIn("Non-Refinery / Dummy Images", _SYSTEM_PROMPT)
        self.assertIn("not part of the refinery", _SYSTEM_PROMPT)
        self.assertIn("cannot be answered", _SYSTEM_PROMPT)

    def test_analyze_image_default_prompt_handles_general_images(self) -> None:
        """Verify AnalyzeImageTool default prompt instructs vision model to describe general/cartoon images."""
        from agents.tools.analyze_image import AnalyzeImageTool
        from generation.vision_provider import VisionProvider
        mock_provider = MagicMock(spec=VisionProvider)
        mock_provider._model = "gemma3:4b"
        tool = AnalyzeImageTool(mock_provider)

        # Call with temp image
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            temp_path = f.name

        try:
            import asyncio
            asyncio.run(tool.execute({"image_path": temp_path}))
            mock_provider.describe_image.assert_called_once()
            called_prompt = mock_provider.describe_image.call_args[1]["prompt"]
            self.assertIn("general, cartoon, meme", called_prompt)
            self.assertIn("non-industrial", called_prompt)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_orchestrator_explains_dummy_image_with_disclaimer(self) -> None:
        """Verify orchestrator formats description and disclaimer for dummy/cartoon images."""
        from agents.orchestrator import AgentOrchestrator
        from agents.ollama_agent_provider import OllamaChatResponse, OllamaToolCall
        from agents.tool_interface import ToolResult
        from agents.tools.analyze_image import AnalyzeImageResult

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_executor = MagicMock()

        # Turn 1: LLM decides to call analyze_image
        # Turn 2: LLM receives vision description and gives final answer describing Tom the cat + non-refinery disclaimer
        mock_llm.chat.side_effect = [
            OllamaChatResponse(
                content="",
                tool_calls=[
                    OllamaToolCall(
                        name="analyze_image",
                        arguments={"image_path": "uploads/cat.jpg"},
                    )
                ],
            ),
            OllamaChatResponse(
                content=(
                    "The image depicts Tom the cat from the classic cartoon animation 'Tom & Jerry' "
                    "standing upright in a room. Please note that this image is not part of the refinery "
                    "facility or industrial operations in any way, so questions based on it cannot be answered "
                    "in a plant operational context."
                ),
                tool_calls=[],
            ),
        ]

        # Executor returns tool result
        from unittest.mock import AsyncMock
        mock_executor.execute = AsyncMock(return_value=ToolResult(
            tool_name="analyze_image",
            success=True,
            result=AnalyzeImageResult(
                "Image Analysis (gemma3:4b): Cartoon cat Tom standing in an animated room.",
                model="gemma3:4b",
            ),
        ))

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_registry,
            tool_executor=mock_executor,
        )

        result = orchestrator.run(query="tell me what's in this image")
        self.assertIsNotNone(result)
        self.assertIn("Tom the cat", result.answer)
        self.assertIn("not part of the refinery", result.answer)
        self.assertIn("cannot be answered", result.answer)
        self.assertNotIn("I'm happy to help you with your refinery operation questions", result.answer)

    def test_try_parse_comma_separated_tool_call(self) -> None:
        """Verify OllamaAgentProvider parses comma-separated tool call syntax emitted by small models."""
        from agents.ollama_agent_provider import OllamaAgentProvider
        raw_text = r'"analyze_image", "image_path": "D:\\data\\storage\\documents\\test\\P\&ID.webp"'
        tc = OllamaAgentProvider._try_parse_content_tool_call(raw_text)
        self.assertIsNotNone(tc)
        self.assertEqual(tc.name, "analyze_image")
        self.assertEqual(tc.arguments.get("image_path"), r"D:\data\storage\documents\test\P&ID.webp")

    def test_try_parse_function_call_syntax(self) -> None:
        """Verify OllamaAgentProvider parses function call syntax like analyze_pid(image_path='...')."""
        from agents.ollama_agent_provider import OllamaAgentProvider
        raw_text = 'analyze_pid(image_path="documents/pid.png", focus_equipment="P-101")'
        tc = OllamaAgentProvider._try_parse_content_tool_call(raw_text)
        self.assertIsNotNone(tc)
        self.assertEqual(tc.name, "analyze_pid")
        self.assertEqual(tc.arguments.get("image_path"), "documents/pid.png")
        self.assertEqual(tc.arguments.get("focus_equipment"), "P-101")

    def test_orchestrator_guards_against_raw_tool_call_string(self) -> None:
        """Verify orchestrator replaces raw tool string with actual visual findings if LLM outputs raw syntax."""
        from agents.orchestrator import AgentOrchestrator
        from agents.ollama_agent_provider import OllamaChatResponse
        from agents.tool_interface import ToolResult

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_executor = MagicMock()

        # Turn 1: LLM returns raw tool text as answer
        mock_llm.chat.return_value = OllamaChatResponse(
            content='"analyze_image", "image_path": "P&ID.webp"',
            tool_calls=[],
        )

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_registry,
            tool_executor=mock_executor,
        )

        result = orchestrator.run(query="explain this diagram")
        # Should not output raw syntax
        self.assertFalse(result.answer.startswith('"analyze_image"'))


if __name__ == "__main__":
    unittest.main()

