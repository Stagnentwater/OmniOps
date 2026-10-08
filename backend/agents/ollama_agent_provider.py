"""Ollama Agent Provider — native tool calling via /api/chat.

This provider communicates with a local Ollama instance using the
native /api/chat endpoint which supports the ``tools`` parameter
for Llama 3.2 function calling.

This is separate from the existing OllamaLLMProvider (which uses
/api/generate) and OpenRouterLLMProvider (which uses /v1/chat/completions).
Neither of those support tool calling.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OllamaToolCall:
    """A single tool call parsed from an Ollama response."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class OllamaChatResponse:
    """Parsed response from Ollama /api/chat.

    Either ``content`` is populated (final text answer) or
    ``tool_calls`` is populated (tool invocation requests).
    Both may be empty if the model returns an empty response.
    """

    content: str
    tool_calls: tuple[OllamaToolCall, ...] = ()
    model: str = ""
    total_duration_ns: int = 0
    eval_count: int = 0

    @property
    def has_tool_calls(self) -> bool:
        """True if the response contains tool call requests."""
        return len(self.tool_calls) > 0


class OllamaAgentProvider:
    """Communicates with Ollama /api/chat for tool-calling agent loops.

    Supports:
    - Sending tool definitions to the LLM
    - Parsing tool_calls from the LLM response
    - Sending tool results back (role: tool messages)
    - Plain text responses (no tool call)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> OllamaChatResponse:
        """Send a chat request to Ollama with optional tool definitions.

        Args:
            messages: The conversation message history in Ollama format.
                Each message has 'role' and 'content' keys.
                Role can be: 'system', 'user', 'assistant', or 'tool'.
            tools: Optional list of tool definitions in Ollama format.
                Each tool has 'type' and 'function' keys.

        Returns:
            An OllamaChatResponse with either content or tool_calls.

        Raises:
            RuntimeError: If the Ollama API call fails.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.error("Ollama agent call failed: %s", e)
            raise RuntimeError(
                f"Failed to communicate with Ollama at {self._base_url}: {e}"
            ) from e

        return self._parse_response(result)

    def _parse_response(self, raw: dict[str, Any]) -> OllamaChatResponse:
        """Parse the raw Ollama /api/chat JSON response.

        Handles both plain text responses and tool call responses.
        """
        message = raw.get("message", {})
        content = message.get("content", "")
        model = raw.get("model", self._model)
        total_duration = raw.get("total_duration", 0)
        eval_count = raw.get("eval_count", 0)

        # Parse tool calls if present
        raw_tool_calls = message.get("tool_calls", [])
        tool_calls: list[OllamaToolCall] = []

        for tc in raw_tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            arguments = func.get("arguments", {})

            # Arguments may be a string (JSON) or already parsed dict
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, ValueError):
                    logger.warning(
                        "Failed to parse tool call arguments as JSON: %s",
                        arguments,
                    )
                    arguments = {"raw_input": arguments}

            if name:
                tool_calls.append(OllamaToolCall(name=name, arguments=arguments))

        # Fallback: small models (e.g., llama3.2) sometimes output JSON tool calls in content
        if not tool_calls and content.strip():
            fallback_tc = self._try_parse_content_tool_call(content)
            if fallback_tc is not None:
                tool_calls.append(fallback_tc)
                content = ""

        return OllamaChatResponse(
            content=content.strip(),
            tool_calls=tuple(tool_calls),
            model=model,
            total_duration_ns=total_duration,
            eval_count=eval_count,
        )

    @staticmethod
    def _try_parse_content_tool_call(content: str) -> OllamaToolCall | None:
        """Attempt to extract a JSON tool call if an LLM outputs raw JSON in content."""
        text = content.strip()
        cb_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidates = [cb_match.group(1)] if cb_match else []
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match and json_match.group(0) not in candidates:
            candidates.append(json_match.group(0))

        known_tools = {
            "search_documents",
            "search_knowledge_graph",
            "calculate",
            "analyze_image",
            "analyze_pid",
            "system_status",
        }
        for cand in candidates:
            try:
                data = json.loads(cand)
                if isinstance(data, dict):
                    name = data.get("name") or data.get("tool")
                    if isinstance(name, str) and name in known_tools:
                        args = data.get("parameters") or data.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {"raw_input": args}
                        elif not isinstance(args, dict):
                            args = {}
                        return OllamaToolCall(name=name, arguments=args)
            except Exception:
                continue
        return None
