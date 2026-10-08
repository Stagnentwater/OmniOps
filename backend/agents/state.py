"""Agent execution state that accumulates across tool invocations.

AgentState is the mutable context that evolves during a single agent
execution. It carries the full message history (for the LLM), the
record of tool invocations, safety counters, and the final answer.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from agents.tool_interface import ToolResult


@dataclass
class AgentState:
    """Mutable state for a single agent execution.

    Created at the start of each user query and passed through the
    agent loop. Accumulates tool results, tracks iterations, and
    enforces safety limits.
    """

    # Identity
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""

    # Input
    user_query: str = ""

    # LLM message history (Ollama /api/chat format)
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Tool execution history
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)

    # Safety counters
    iteration_count: int = 0
    max_iterations: int = 8
    started_at: float = field(default_factory=time.time)
    timeout_seconds: float = 120.0

    # Outcome
    final_answer: str | None = None
    error: str | None = None

    @property
    def is_timed_out(self) -> bool:
        """Check whether the execution has exceeded the timeout."""
        return (time.time() - self.started_at) > self.timeout_seconds

    @property
    def is_iteration_limit_reached(self) -> bool:
        """Check whether the max iteration limit has been reached."""
        return self.iteration_count >= self.max_iterations

    @property
    def is_finished(self) -> bool:
        """Check whether the execution has reached a terminal state."""
        return (
            self.final_answer is not None
            or self.error is not None
            or self.is_timed_out
            or self.is_iteration_limit_reached
        )

    @property
    def elapsed_seconds(self) -> float:
        """Return the number of seconds since the execution started."""
        return time.time() - self.started_at

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Record a tool invocation for audit and duplicate detection."""
        self.tool_calls.append({
            "iteration": self.iteration_count,
            "tool_name": tool_name,
            "arguments": arguments,
            "timestamp": time.time(),
        })

    def has_duplicate_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Check if this exact tool call has already been made.

        Prevents the agent from making the same call repeatedly,
        which is a common failure mode for small LLMs.
        """
        for prior in self.tool_calls:
            if prior["tool_name"] == tool_name and prior["arguments"] == arguments:
                return True
        return False

    @property
    def consecutive_errors(self) -> int:
        """Count consecutive tool errors from the most recent results."""
        count = 0
        for result in reversed(self.tool_results):
            if not result.success:
                count += 1
            else:
                break
        return count
