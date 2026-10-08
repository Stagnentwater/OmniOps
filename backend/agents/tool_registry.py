"""Tool registry for agent tool discovery and schema export.

The ToolRegistry is the single source of truth for which tools
the agent can invoke. The LLM receives tool definitions from
this registry via ``get_definitions()``.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.tool_interface import Tool, ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all agent-accessible tools.

    Responsibilities:
    - Register and unregister tools by name
    - Retrieve a tool by name for execution
    - Export all tool definitions for the LLM
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool, keyed by its definition name.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered. "
                f"Unregister it first or use a different name."
            )
        self._tools[name] = tool
        logger.info("ToolRegistry: registered tool '%s'", name)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry.

        Raises:
            KeyError: If the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        del self._tools[name]
        logger.info("ToolRegistry: unregistered tool '%s'", name)

    def get(self, name: str) -> Tool:
        """Retrieve a registered tool by name.

        Raises:
            KeyError: If the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(
                f"Tool '{name}' is not registered. "
                f"Available tools: {list(self._tools.keys())}"
            )
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return list(self._tools.keys())

    def get_definitions(self) -> list[ToolDefinition]:
        """Return all tool definitions (for logging/introspection)."""
        return [tool.definition for tool in self._tools.values()]

    def get_ollama_schemas(self) -> list[dict[str, Any]]:
        """Return all tool definitions serialized for the Ollama API.

        This is the list passed as the ``tools`` parameter in
        the /api/chat request body.
        """
        return [tool.definition.to_ollama_schema() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
