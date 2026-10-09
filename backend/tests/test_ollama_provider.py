"""Unit tests for OllamaLLMProvider and orchestrator provider selection."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock

from generation.generation_models import PromptPackage, RawGeneration
from generation.ollama_provider import OllamaLLMProvider


def _mock_urlopen(response_body: dict):
    """Create a mock for urllib.request.urlopen returning the given JSON."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestOllamaLLMProvider(unittest.TestCase):
    """Tests for OllamaLLMProvider."""

    def setUp(self):
        self.provider = OllamaLLMProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
            timeout_seconds=30.0,
        )

    @patch("generation.ollama_provider.urllib.request.urlopen")
    def test_successful_generate(self, mock_urlopen):
        """Test generating answer without conversation history."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "response": "The operational status is normal. [Context #1]",
            "total_duration": 1234567,
            "prompt_eval_count": 50,
            "eval_count": 25,
        })

        package = PromptPackage(
            system_prompt="You are an industrial assistant.",
            user_prompt="What is the operational status?",
            formatted_context="[Context #1] All systems nominal.",
            metadata={},
        )

        result = self.provider.generate(package)

        self.assertIsInstance(result, RawGeneration)
        self.assertEqual(result.raw_response, "The operational status is normal. [Context #1]")
        self.assertEqual(result.metadata["model"], "llama3.2")
        self.assertEqual(result.metadata["eval_count"], 25)

    @patch("generation.ollama_provider.urllib.request.urlopen")
    def test_generate_with_conversation_history(self, mock_urlopen):
        """Test generating answer with conversation history included."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "response": "Affirmative.",
        })

        package = PromptPackage(
            system_prompt="You are an industrial assistant.",
            user_prompt="Any new risks?",
            formatted_context="[Context #1] Boiler pressure 12 bar.",
            metadata={},
            conversation_history="User: Hello\nAssistant: Greetings.",
        )

        result = self.provider.generate(package)
        self.assertEqual(result.raw_response, "Affirmative.")

        # Verify payload sent to Ollama
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        data = json.loads(req.data.decode("utf-8"))
        self.assertIn("Previous Conversation", data["prompt"])
        self.assertIn("Boiler pressure 12 bar", data["prompt"])
        self.assertIn("Any new risks?", data["prompt"])

    @patch("generation.ollama_provider.urllib.request.urlopen")
    def test_connection_error_raises_runtime_error(self, mock_urlopen):
        """Test URLError is caught and re-raised as RuntimeError."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        package = PromptPackage(
            system_prompt="sys",
            user_prompt="query",
            formatted_context="ctx",
            metadata={},
        )

        with self.assertRaises(RuntimeError) as ctx:
            self.provider.generate(package)
        self.assertIn("Failed to communicate with LLM provider", str(ctx.exception))


class TestDependenciesProviderSelection(unittest.TestCase):
    """Test that get_query_orchestrator selects OllamaLLMProvider for local settings."""

    @classmethod
    def setUpClass(cls) -> None:
        import sys
        for mod in [
            "psycopg", "psycopg.rows",
            "neo4j",
            "qdrant_client", "qdrant_client.models",
            "sentence_transformers",
            "tenacity",
            "httpx",
        ]:
            if mod not in sys.modules:
                sys.modules[mod] = MagicMock()

    @patch("dependencies._get_connections")
    @patch("dependencies.SentenceTransformerEmbeddingProvider")
    @patch("dependencies.get_settings")
    def test_selects_ollama_when_key_is_ollama_local(
        self, mock_get_settings, mock_embed, mock_conns
    ):
        mock_settings = MagicMock()
        mock_settings.openrouter.api_key = "ollama-local"
        mock_settings.openrouter.base_url = "http://localhost:11434/v1"
        mock_settings.models.ollama_base_url = "http://localhost:11434"
        mock_settings.models.reasoning_model = "llama3.2"
        mock_settings.embedding.model_name = "test-model"
        mock_settings.query.conversation_history_limit = 5
        mock_get_settings.return_value = mock_settings

        mock_conns.return_value = (MagicMock(), MagicMock())

        from dependencies import get_query_orchestrator
        orchestrator = get_query_orchestrator()

        self.assertIsInstance(
            orchestrator._generation_service._llm_provider,
            OllamaLLMProvider
        )
