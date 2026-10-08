"""Dummy test tool for proving the agent loop.

Returns system status info. Used during AGENT-CORE-001 to verify
the full agent loop without real infrastructure dependencies.
"""

from __future__ import annotations

import time
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult


class SystemStatusTool(Tool):
    """Returns basic system status information.

    This is a lightweight tool used to prove the agent loop works:
    LLM → tool call → tool result → LLM → final answer.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_system_status",
            description=(
                "Returns the current system status of OmniOps, "
                "including uptime, service health, and version. "
                "Use this tool when the user asks about system status or health."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "include_details": {
                        "type": "boolean",
                        "description": "If true, include detailed service status.",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Return mock system status."""
        include_details = arguments.get("include_details", False)

        status = {
            "system": "OmniOps",
            "version": "1.5.0",
            "status": "operational",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if include_details:
            status["services"] = {
                "postgres": "healthy",
                "neo4j": "healthy",
                "qdrant": "healthy",
                "redis": "healthy",
                "ollama": "connected",
            }

        return ToolResult(
            tool_name="get_system_status",
            success=True,
            result=str(status),
        )
