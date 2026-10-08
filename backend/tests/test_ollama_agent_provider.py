"""Tests for the Ollama Agent Provider (tool calling adapter)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

from agents.ollama_agent_provider import (
    OllamaAgentProvider,
    OllamaChatResponse,
    OllamaToolCall,
)


def _mock_urlopen(response_body: dict):
    """Create a mock for urllib.request.urlopen returning the given JSON."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestOllamaAgentProvider(unittest.TestCase):
    """Tests for OllamaAgentProvider."""

    def setUp(self):
        self.provider = OllamaAgentProvider(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_plain_text_response(self, mock_urlopen):
        """Test parsing a response with no tool calls."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you?",
            },
            "total_duration": 1234567890,
            "eval_count": 15,
        })

        response = self.provider.chat(
            messages=[{"role": "user", "content": "Hello"}],
        )

        self.assertIsInstance(response, OllamaChatResponse)
        self.assertEqual(response.content, "Hello! How can I help you?")
        self.assertFalse(response.has_tool_calls)
        self.assertEqual(len(response.tool_calls), 0)
        self.assertEqual(response.model, "llama3.2")

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_tool_call_response(self, mock_urlopen):
        """Test parsing a response with tool calls."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_documents",
                            "arguments": {"query": "pump pressure", "top_k": 5},
                        }
                    }
                ],
            },
            "total_duration": 2345678901,
        })

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Search documents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

        response = self.provider.chat(
            messages=[{"role": "user", "content": "What is the pressure of P-101?"}],
            tools=tools,
        )

        self.assertTrue(response.has_tool_calls)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "search_documents")
        self.assertEqual(response.tool_calls[0].arguments["query"], "pump pressure")

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_multiple_tool_calls(self, mock_urlopen):
        """Test parsing a response with multiple tool calls."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_documents",
                            "arguments": {"query": "pump specs"},
                        }
                    },
                    {
                        "function": {
                            "name": "search_knowledge_graph",
                            "arguments": {"query": "P-101"},
                        }
                    },
                ],
            },
        })

        response = self.provider.chat(
            messages=[{"role": "user", "content": "Tell me about P-101"}],
        )

        self.assertTrue(response.has_tool_calls)
        self.assertEqual(len(response.tool_calls), 2)
        self.assertEqual(response.tool_calls[0].name, "search_documents")
        self.assertEqual(response.tool_calls[1].name, "search_knowledge_graph")

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_string_arguments_parsed(self, mock_urlopen):
        """Test that string-encoded arguments are parsed as JSON."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "calculate",
                            "arguments": '{"expression": "2 + 2"}',
                        }
                    }
                ],
            },
        })

        response = self.provider.chat(
            messages=[{"role": "user", "content": "Calculate 2+2"}],
        )

        self.assertTrue(response.has_tool_calls)
        self.assertEqual(
            response.tool_calls[0].arguments["expression"],
            "2 + 2",
        )

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_request_payload_contains_tools(self, mock_urlopen):
        """Verify the HTTP request body includes tools when provided."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "ok"},
        })

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        self.provider.chat(
            messages=[{"role": "user", "content": "test"}],
            tools=tools,
        )

        # Verify the request was made with tools in payload
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertIn("tools", body)
        self.assertEqual(body["tools"][0]["function"]["name"], "test_tool")
        self.assertEqual(body["model"], "llama3.2")
        self.assertFalse(body["stream"])

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_request_without_tools(self, mock_urlopen):
        """Verify the HTTP request body omits tools when none provided."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "hi"},
        })

        self.provider.chat(
            messages=[{"role": "user", "content": "hello"}],
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("tools", body)

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_connection_error_raises_runtime_error(self, mock_urlopen):
        """Test that connection failures raise RuntimeError."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(RuntimeError) as ctx:
            self.provider.chat(
                messages=[{"role": "user", "content": "test"}],
            )

        self.assertIn("Failed to communicate with Ollama", str(ctx.exception))

    @patch("agents.ollama_agent_provider.urllib.request.urlopen")
    def test_empty_tool_call_name_ignored(self, mock_urlopen):
        """Tool calls with empty names should be silently skipped."""
        mock_urlopen.return_value = _mock_urlopen({
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "thinking...",
                "tool_calls": [
                    {"function": {"name": "", "arguments": {}}},
                    {"function": {"name": "valid_tool", "arguments": {"x": 1}}},
                ],
            },
        })

        response = self.provider.chat(
            messages=[{"role": "user", "content": "test"}],
        )

        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "valid_tool")


class TestOllamaToolCall(unittest.TestCase):
    """Tests for OllamaToolCall data contract."""

    def test_frozen(self):
        tc = OllamaToolCall(name="test", arguments={"x": 1})
        with self.assertRaises(AttributeError):
            tc.name = "modified"  # type: ignore[misc]


class TestOllamaChatResponse(unittest.TestCase):
    """Tests for OllamaChatResponse data contract."""

    def test_has_tool_calls_true(self):
        resp = OllamaChatResponse(
            content="",
            tool_calls=(OllamaToolCall("t", {}),),
        )
        self.assertTrue(resp.has_tool_calls)

    def test_has_tool_calls_false(self):
        resp = OllamaChatResponse(content="hello")
        self.assertFalse(resp.has_tool_calls)


if __name__ == "__main__":
    unittest.main()
