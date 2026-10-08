"""Centralized tool executor for dispatching agent tool calls.

The ToolExecutor is the ONLY path from the agent loop to actual
tool execution. The LLM never directly invokes Python functions.

Flow:
    LLM → Tool Call → ToolExecutor → ToolRegistry → Tool → Service
"""

from __future__ import annotations

import logging
import time
from typing import Any

from agents.tool_interface import ToolResult
from agents.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Dispatches tool calls to registered tools and returns structured results.

    Responsibilities:
    - Resolve tool name against ToolRegistry
    - Validate that the tool exists
    - Execute the tool with provided arguments
    - Capture timing, errors, and structured results
    - Never allow unregistered or unknown tools to execute
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool call and return a structured ToolResult.

        Args:
            tool_name: The name of the tool to invoke.
            arguments: The parsed arguments from the LLM.

        Returns:
            A ToolResult with success/failure status, result data,
            and execution timing.
        """
        start_time = time.time()

        # 1. Resolve tool from registry
        if tool_name not in self._registry:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.warning(
                "ToolExecutor: unknown tool '%s'. Available: %s",
                tool_name,
                self._registry.list_tools(),
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Unknown tool '{tool_name}'. Available tools: {self._registry.list_tools()}",
                execution_time_ms=elapsed_ms,
            )

        tool = self._registry.get(tool_name)

        # 2. Execute with error handling
        try:
            logger.info(
                "ToolExecutor: executing '%s' with args: %s",
                tool_name,
                _truncate_args(arguments),
            )
            result = await tool.execute(arguments)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                "ToolExecutor: '%s' completed in %.0fms (success=%s)",
                tool_name,
                elapsed_ms,
                result.success,
            )

            # Override execution time with our measured value
            return ToolResult(
                tool_name=result.tool_name,
                success=result.success,
                result=result.result,
                error=result.error,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                "ToolExecutor: '%s' raised exception: %s",
                tool_name,
                str(e),
                exc_info=True,
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Tool execution error: {str(e)}",
                execution_time_ms=elapsed_ms,
            )


def _truncate_args(arguments: dict[str, Any], max_len: int = 200) -> str:
    """Truncate argument representation for logging.

    Prevents sensitive or very large data from flooding logs.
    """
    text = str(arguments)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
