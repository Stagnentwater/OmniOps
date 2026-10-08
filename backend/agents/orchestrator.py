"""Agent Orchestrator — the central agentic runtime.

Implements the full agent loop:
    DISCOVER → DECIDE → CALL → EXECUTE → RETURN → UPDATE → REASON → NEXT

The orchestrator:
1. Initializes AgentState with the user query
2. Calls Llama 3.2 with available tool definitions
3. If the LLM returns a final answer → return
4. If the LLM returns tool_calls → execute via ToolExecutor
5. Append tool results to message history
6. Re-invoke Llama with updated context
7. Repeat until final answer or safety limit
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.ollama_agent_provider import OllamaAgentProvider, OllamaChatResponse
from agents.state import AgentState
from agents.tool_executor import ToolExecutor
from agents.tool_interface import ToolResult
from agents.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# Maximum consecutive tool errors before forcing a fallback answer
_MAX_CONSECUTIVE_ERRORS = 2

# System prompt for the agent
_SYSTEM_PROMPT = """You are OmniOps, an Industrial Intelligence Assistant for confidential refinery and industrial operations.

You have access to tools that help you answer questions accurately. Use them when appropriate.

IMPORTANT RULES:
1. For factual questions about documents, equipment, or processes: use search_documents or search_knowledge_graph.
2. For numerical calculations, unit conversions, or engineering equations: use the calculate tool. NEVER calculate numbers yourself.
3. For image analysis: use analyze_image or analyze_pid.
4. For simple greetings or general conversation: respond directly WITHOUT using any tools.
5. Always base your final answer on tool results, not assumptions.
6. If a tool returns an error, you may try a different approach or explain the limitation.
7. Be concise and professional in your responses.
8. Cite sources when using retrieved documents."""


@dataclass
class AgentResult:
    """Final result of an agent execution."""

    answer: str
    tool_calls_made: list[dict[str, Any]]
    iterations: int
    execution_time_seconds: float
    error: str | None = None


class AgentOrchestrator:
    """Central agentic runtime that coordinates LLM reasoning and tool execution.

    Usage:
        registry = ToolRegistry()
        registry.register(SearchDocumentsTool(...))
        registry.register(CalculateTool(...))

        executor = ToolExecutor(registry)
        provider = OllamaAgentProvider(...)
        orchestrator = AgentOrchestrator(provider, registry, executor)

        result = orchestrator.run("What is the pressure of P-101?")
    """

    def __init__(
        self,
        llm_provider: OllamaAgentProvider,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        max_iterations: int = 8,
        timeout_seconds: float = 120.0,
        system_prompt: str = _SYSTEM_PROMPT,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._llm = llm_provider
        self._registry = tool_registry
        self._executor = tool_executor
        self._max_iterations = max_iterations
        self._timeout = timeout_seconds
        self._system_prompt = system_prompt
        self._on_event = on_event or (lambda stage, data: None)

    def run(
        self,
        query: str,
        conversation_id: str = "",
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
        """Execute the full agent loop for a user query.

        Args:
            query: The user's question.
            conversation_id: Optional session ID for tracking.
            conversation_history: Optional prior conversation turns
                (list of dicts with 'role' and 'content').

        Returns:
            An AgentResult with the final answer and execution metadata.
        """
        # Initialize state
        state = AgentState(
            conversation_id=conversation_id,
            user_query=query,
            max_iterations=self._max_iterations,
            timeout_seconds=self._timeout,
        )

        # Build initial messages
        state.messages.append({
            "role": "system",
            "content": self._system_prompt,
        })

        # Add conversation history if provided
        if conversation_history:
            for turn in conversation_history:
                state.messages.append({
                    "role": turn["role"],
                    "content": turn["content"],
                })

        # Add current user query
        state.messages.append({
            "role": "user",
            "content": query,
        })

        self._emit("AGENT_STARTED", {
            "execution_id": state.execution_id,
            "query": query,
        })

        logger.info(
            "Agent started: execution_id=%s, query='%s', max_iter=%d",
            state.execution_id,
            query[:100],
            self._max_iterations,
        )

        # === AGENT LOOP ===
        while not state.is_finished:
            state.iteration_count += 1

            logger.info(
                "Agent iteration %d/%d (execution=%s)",
                state.iteration_count,
                state.max_iterations,
                state.execution_id,
            )

            # Safety: check timeout
            if state.is_timed_out:
                logger.warning("Agent timed out after %.1fs", state.elapsed_seconds)
                state.error = "Agent execution timed out"
                self._emit("AGENT_TIMEOUT", {
                    "elapsed": state.elapsed_seconds,
                })
                break

            # Safety: check consecutive errors
            if state.consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                logger.warning(
                    "Agent hit %d consecutive tool errors, forcing fallback",
                    state.consecutive_errors,
                )
                state.final_answer = self._build_fallback_answer(state)
                self._emit("AGENT_FALLBACK", {
                    "reason": "consecutive_tool_errors",
                    "count": state.consecutive_errors,
                })
                break

            # 1. Call LLM with tools
            self._emit("REASONING", {
                "iteration": state.iteration_count,
            })

            try:
                tools = self._registry.get_ollama_schemas()
                response = self._llm.chat(
                    messages=state.messages,
                    tools=tools if tools else None,
                )
            except RuntimeError as e:
                logger.error("LLM call failed: %s", e)
                state.error = f"LLM communication failed: {e}"
                self._emit("AGENT_ERROR", {"error": str(e)})
                break

            # 2. Check if final answer (no tool calls)
            if not response.has_tool_calls:
                state.final_answer = response.content or "I was unable to generate an answer."
                state.messages.append({
                    "role": "assistant",
                    "content": state.final_answer,
                })
                self._emit("FINAL_ANSWER", {
                    "iteration": state.iteration_count,
                })
                logger.info(
                    "Agent reached final answer at iteration %d",
                    state.iteration_count,
                )
                break

            # 3. Process tool calls
            # Add assistant message with tool_calls to history
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in response.tool_calls
                ],
            }
            state.messages.append(assistant_msg)

            for tc in response.tool_calls:
                # Duplicate detection
                if state.has_duplicate_tool_call(tc.name, tc.arguments):
                    logger.warning(
                        "Duplicate tool call detected: %s(%s). Skipping.",
                        tc.name,
                        tc.arguments,
                    )
                    # Add a synthetic error result
                    dup_result = ToolResult(
                        tool_name=tc.name,
                        success=False,
                        result=None,
                        error=f"Duplicate call to '{tc.name}' with same arguments. Try different arguments or provide a final answer.",
                    )
                    state.tool_results.append(dup_result)
                    state.messages.append({
                        "role": "tool",
                        "content": dup_result.to_message_content(),
                    })
                    continue

                # Record the tool call
                state.add_tool_call(tc.name, tc.arguments)

                self._emit("TOOL_EXECUTING", {
                    "tool": tc.name,
                    "iteration": state.iteration_count,
                })

                # Execute via ToolExecutor
                result = self._execute_tool_sync(tc.name, tc.arguments)

                state.tool_results.append(result)

                # Add tool result to messages for LLM re-reasoning
                state.messages.append({
                    "role": "tool",
                    "content": result.to_message_content(),
                })

                self._emit("TOOL_COMPLETED", {
                    "tool": tc.name,
                    "success": result.success,
                    "execution_time_ms": result.execution_time_ms,
                    "iteration": state.iteration_count,
                })

                logger.info(
                    "Tool '%s' completed: success=%s, time=%.0fms",
                    tc.name,
                    result.success,
                    result.execution_time_ms,
                )

            # Safety: check iteration limit before next loop
            if state.is_iteration_limit_reached:
                logger.warning(
                    "Agent reached max iterations (%d)", state.max_iterations
                )
                state.final_answer = self._build_fallback_answer(state)
                self._emit("AGENT_MAX_ITERATIONS", {
                    "max": state.max_iterations,
                })
                break

        # === BUILD RESULT ===
        elapsed = state.elapsed_seconds
        self._emit("AGENT_COMPLETED", {
            "execution_id": state.execution_id,
            "iterations": state.iteration_count,
            "tool_calls": len(state.tool_calls),
            "elapsed_seconds": elapsed,
        })

        answer = state.final_answer or state.error or "Agent execution failed without producing an answer."

        logger.info(
            "Agent completed: execution_id=%s, iterations=%d, tools=%d, time=%.1fs",
            state.execution_id,
            state.iteration_count,
            len(state.tool_calls),
            elapsed,
        )

        return AgentResult(
            answer=answer,
            tool_calls_made=[
                {"tool": tc["tool_name"], "arguments": tc["arguments"]}
                for tc in state.tool_calls
            ],
            iterations=state.iteration_count,
            execution_time_seconds=elapsed,
            error=state.error,
        )

    def _build_fallback_answer(self, state: AgentState) -> str:
        """Build a best-effort answer when the agent hits a safety limit.

        Uses whatever tool results have been collected so far.
        """
        successful_results = [
            r for r in state.tool_results if r.success
        ]

        if successful_results:
            context = "\n\n".join(
                f"[{r.tool_name}]: {str(r.result)[:500]}"
                for r in successful_results
            )
            return (
                f"Based on the information I was able to gather:\n\n{context}\n\n"
                f"Note: I reached the maximum processing limit and may not have "
                f"a complete answer."
            )

        return (
            "I was unable to fully process your request within the allowed "
            "processing steps. Please try rephrasing your question or "
            "breaking it into smaller parts."
        )

    def _execute_tool_sync(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool coroutine synchronously, handling any event loop state."""
        coro = self._executor.execute(tool_name, arguments)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            try:
                curr_loop = asyncio.get_event_loop()
                if curr_loop.is_closed():
                    curr_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(curr_loop)
            except RuntimeError:
                curr_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(curr_loop)
            return curr_loop.run_until_complete(coro)

    def _emit(self, stage: str, data: dict[str, Any]) -> None:
        """Emit an agent execution event."""
        try:
            self._on_event(stage, data)
        except Exception:
            logger.debug("Event emission failed for stage '%s'", stage, exc_info=True)
