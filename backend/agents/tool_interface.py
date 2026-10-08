"""Immutable data contracts for the agent tool interface.

Defines the abstract Tool base class, ToolDefinition (schema for LLM),
and ToolResult (structured execution output). Every agent-accessible
capability must implement the Tool interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """Schema sent to the LLM for tool selection.

    Conforms to the Ollama /api/chat tools format:
    {
        "type": "function",
        "function": {
            "name": ...,
            "description": ...,
            "parameters": { JSON Schema }
        }
    }
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def to_ollama_schema(self) -> dict[str, Any]:
        """Serialize to the Ollama tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True)
class ToolResult:
    """Structured result from tool execution.

    Every tool execution returns this, whether successful or not.
    The agent loop uses ``success`` to decide how to proceed.
    """

    tool_name: str
    success: bool
    result: Any
    error: str | None = None
    execution_time_ms: float = 0.0

    def to_message_content(self) -> str:
        """Format the result as a string for the LLM tool-result message."""
        if self.success:
            return str(self.result)
        return f"Tool '{self.tool_name}' failed: {self.error}"


class Tool(ABC):
    """Abstract base class for all agent-accessible tools.

    Subclasses must implement ``definition`` and ``execute``.
    The AgentOrchestrator discovers tools through the ToolRegistry,
    never by direct import.
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool schema for LLM discovery."""

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute the tool with validated arguments.

        Args:
            arguments: The parsed arguments from the LLM tool call.

        Returns:
            A ToolResult indicating success or failure.
        """
