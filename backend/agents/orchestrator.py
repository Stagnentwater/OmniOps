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
import uuid
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


def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive keys from tool arguments for UI safety."""
    if not isinstance(arguments, dict):
        return {}
    sensitive_patterns = {"password", "secret", "token", "key", "auth", "credential"}
    sanitized: dict[str, Any] = {}
    for k, v in arguments.items():
        if any(pat in k.lower() for pat in sensitive_patterns):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > 200:
            sanitized[k] = v[:200] + "..."
        else:
            sanitized[k] = v
    return sanitized


def _generate_tool_started_message(tool_name: str, args: dict[str, Any]) -> str:
    """Generate concise, user-safe activity message for tool execution start."""
    if tool_name == "search_documents":
        q = args.get("query", "")
        if q:
            clean_q = str(q).strip().strip("'\"")[:40]
            return f"Searching technical documents for '{clean_q}'..."
        return "Searching technical documents..."
    elif tool_name == "search_knowledge_graph":
        target = args.get("query") or args.get("entity_id") or ""
        if target:
            clean_t = str(target).strip().strip("'\"")[:40]
            return f"Checking process graph for '{clean_t}'..."
        return "Checking process graph relationships..."
    elif tool_name == "calculate":
        return "Running deterministic calculation..."
    elif tool_name == "analyze_image":
        return "Analyzing equipment image with Gemma 3..."
    elif tool_name == "analyze_pid":
        return "Analyzing Piping & Instrumentation Diagram..."
    elif tool_name == "system_status":
        return "Checking system operational status..."
    return f"Running {tool_name}..."


def _generate_tool_completed_message(
    tool_name: str, result: ToolResult, args: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Generate concise, user-safe activity summary and metadata for completed tool."""
    metadata: dict[str, Any] = {}
    if not result.success:
        err = result.error or "Operation failed"
        return f"Tool '{tool_name}' failed: {err}", {"error": err}

    if tool_name == "search_documents":
        chunks = getattr(result.result, "chunks", None)
        count = len(chunks) if chunks is not None else 0
        metadata["result_count"] = count
        if count == 0:
            return "No matching document chunks found.", metadata
        return f"Found {count} relevant document chunk{'s' if count != 1 else ''}.", metadata

    elif tool_name == "search_knowledge_graph":
        entities = getattr(result.result, "entities", None)
        edges = getattr(result.result, "edges", None)
        num_ent = len(entities) if entities is not None else 0
        num_edge = len(edges) if edges is not None else 0
        metadata["entities_count"] = num_ent
        metadata["edges_count"] = num_edge
        if num_ent == 0 and num_edge == 0:
            return "No matching graph entities found.", metadata
        return f"Found {num_ent} entity node(s) and {num_edge} relationship(s).", metadata

    elif tool_name == "calculate":
        raw_res = getattr(result.result, "raw_result", None)
        if raw_res is None:
            raw_res = str(result.result) if result.result is not None else ""
        metadata["result"] = raw_res
        metadata["execution_time_ms"] = result.execution_time_ms
        return f"Calculation completed. Result: {raw_res}", metadata

    elif tool_name == "analyze_image":
        return "Image analysis completed.", metadata

    elif tool_name == "analyze_pid":
        eq = getattr(result.result, "equipment", None)
        conn = getattr(result.result, "connections", None)
        num_eq = len(eq) if eq is not None else 0
        num_conn = len(conn) if conn is not None else 0
        metadata["equipment_count"] = num_eq
        metadata["connections_count"] = num_conn
        return (
            f"P&ID analysis completed: {num_eq} equipment tag(s), {num_conn} connection(s).",
            metadata,
        )

    return f"{tool_name} completed successfully.", metadata


@dataclass
class AgentResult:
    """Final result of an agent execution."""

    answer: str
    tool_calls_made: list[dict[str, Any]]
    iterations: int
    execution_time_seconds: float
    citations: list[dict[str, Any]] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)
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
        chat_repository: Any | None = None,
        max_history_turns: int = 10,
    ) -> None:
        self._llm = llm_provider
        self._registry = tool_registry
        self._executor = tool_executor
        self._max_iterations = max_iterations
        self._timeout = timeout_seconds
        self._system_prompt = system_prompt
        self._on_event = on_event or (lambda stage, data: None)
        self._chat_repository = chat_repository
        self._max_history_turns = max_history_turns

    def run(
        self,
        query: str,
        conversation_id: str = "",
        conversation_history: list[dict[str, Any]] | None = None,
        exclude_message_id: str | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentResult:
        """Execute the full agent loop for a user query.

        Args:
            query: The user's question.
            conversation_id: Optional session ID for tracking and history loading.
            conversation_history: Optional prior conversation turns
                (list of dicts or ChatMessage objects with 'role' and 'content').
            exclude_message_id: Optional message ID to exclude when loading
                history from chat_repository (typically the current turn).
            on_event: Optional per-run event callback.

        Returns:
            An AgentResult with the final answer, citations, and execution metadata.
        """
        # Event emitter for this run
        event_callback = on_event or self._on_event

        def emit(stage: str, data: dict[str, Any] | None = None) -> None:
            payload = dict(data) if data else {}
            if "stage" not in payload:
                payload["stage"] = stage
            if "event_id" not in payload:
                payload["event_id"] = str(uuid.uuid4())
            if "execution_id" not in payload:
                payload["execution_id"] = state.execution_id
            if "timestamp" not in payload:
                payload["timestamp"] = time.time()
            if "status" not in payload:
                payload["status"] = "running"

            # Accumulate user-safe activity events in state.activities
            if "type" in payload and "message" in payload:
                state.activities.append({
                    "id": payload["event_id"],
                    "type": payload["type"],
                    "status": payload.get("status", "running"),
                    "message": payload["message"],
                    "tool": payload.get("tool"),
                    "metadata": payload.get("metadata", {}),
                    "timestamp": payload["timestamp"],
                })

            try:
                event_callback(stage, payload)
            except Exception:
                logger.debug("Event emission failed for stage '%s'", stage, exc_info=True)

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

        # Resolve conversation history with strict bounds
        resolved_history: list[dict[str, str]] = []
        if conversation_history is not None:
            bounded = conversation_history[-self._max_history_turns:]
            for turn in bounded:
                role = turn.get("role") if isinstance(turn, dict) else getattr(turn, "role", None)
                content = turn.get("content") if isinstance(turn, dict) else getattr(turn, "content", None)
                if role in {"user", "assistant"} and content and str(content).strip():
                    resolved_history.append({"role": role, "content": str(content).strip()})
        elif self._chat_repository is not None and conversation_id:
            try:
                messages = self._chat_repository.get_recent_messages(
                    session_id=conversation_id,
                    limit=self._max_history_turns,
                    exclude_message_id=exclude_message_id,
                )
                for msg in messages:
                    role = msg.role if hasattr(msg, "role") else (msg.get("role") if isinstance(msg, dict) else None)
                    content = msg.content if hasattr(msg, "content") else (msg.get("content") if isinstance(msg, dict) else None)
                    if role in {"user", "assistant"} and content and str(content).strip():
                        resolved_history.append({"role": role, "content": str(content).strip()})
            except Exception as e:
                logger.warning(
                    "Failed to load conversation history for session %s: %s",
                    conversation_id,
                    e,
                )

        # Add prior turns
        for turn in resolved_history:
            state.messages.append({
                "role": turn["role"],
                "content": turn["content"],
            })

        # Add current user query
        state.messages.append({
            "role": "user",
            "content": query,
        })

        emit("AGENT_STARTED", {
            "type": "agent_started",
            "status": "running",
            "message": "Analyzing request...",
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
                emit("AGENT_TIMEOUT", {
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
                emit("AGENT_FALLBACK", {
                    "reason": "consecutive_tool_errors",
                    "count": state.consecutive_errors,
                })
                break

            # 1. Call LLM with tools
            emit("REASONING", {
                "type": "reasoning_summary",
                "status": "running",
                "message": "Analyzing request..." if state.iteration_count == 1 else f"Synthesizing findings (step {state.iteration_count})...",
                "iteration": state.iteration_count,
            })
            emit("GENERATING_RESPONSE", {
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
                emit("AGENT_ERROR", {"error": str(e)})
                break

            # 2. Check if final answer (no tool calls)
            if not response.has_tool_calls:
                state.final_answer = response.content or "I was unable to generate an answer."
                state.messages.append({
                    "role": "assistant",
                    "content": state.final_answer,
                })
                emit("FINAL_ANSWER", {
                    "type": "final_answer_started",
                    "status": "running",
                    "message": "Preparing final response...",
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

                start_msg = _generate_tool_started_message(tc.name, tc.arguments)
                emit("TOOL_STARTED", {
                    "type": "tool_started",
                    "tool": tc.name,
                    "status": "running",
                    "message": start_msg,
                    "iteration": state.iteration_count,
                    "metadata": {"arguments": _sanitize_arguments(tc.arguments)},
                })
                emit("TOOL_EXECUTING", {
                    "tool": tc.name,
                    "iteration": state.iteration_count,
                })
                if tc.name == "search_documents":
                    emit("SEARCHING_VECTOR_DB", {})
                elif tc.name == "search_knowledge_graph":
                    emit("EXPANDING_KNOWLEDGE_GRAPH", {})
                elif tc.name == "calculate":
                    calc_code = tc.arguments.get("code") or tc.arguments.get("expression") or ""
                    if calc_code:
                        emit("CODE_GENERATED", {
                            "type": "code_generated",
                            "tool": "calculate",
                            "status": "running",
                            "message": "Generated Python calculation",
                            "metadata": {
                                "language": "python",
                                "code": str(calc_code).strip(),
                            },
                        })
                    emit("CODE_EXECUTION_STARTED", {
                        "type": "code_execution_started",
                        "tool": "calculate",
                        "status": "running",
                        "message": "Running Python calculation in sandbox...",
                        "metadata": {
                            "language": "python",
                            "code": str(calc_code).strip() if calc_code else "",
                        },
                    })

                # Execute via ToolExecutor
                result = self._execute_tool_sync(tc.name, tc.arguments)

                state.tool_results.append(result)

                # Add tool result to messages for LLM re-reasoning
                state.messages.append({
                    "role": "tool",
                    "content": result.to_message_content(),
                })

                if result.success:
                    comp_msg, comp_meta = _generate_tool_completed_message(tc.name, result, tc.arguments)
                    if tc.name == "calculate":
                        calc_code = tc.arguments.get("code") or tc.arguments.get("expression") or ""
                        raw_res = comp_meta.get("result", "")
                        emit("CODE_EXECUTION_COMPLETED", {
                            "type": "code_execution_completed",
                            "tool": "calculate",
                            "status": "completed",
                            "message": f"Calculation completed ({result.execution_time_ms:.0f}ms)",
                            "metadata": {
                                "language": "python",
                                "code": str(calc_code).strip() if calc_code else "",
                                "result": raw_res,
                                "status": "success",
                                "execution_time_ms": result.execution_time_ms,
                            },
                        })
                    emit("TOOL_COMPLETED", {
                        "type": "tool_completed",
                        "tool": tc.name,
                        "status": "completed",
                        "message": comp_msg,
                        "success": True,
                        "execution_time_ms": result.execution_time_ms,
                        "iteration": state.iteration_count,
                        "metadata": comp_meta,
                    })
                else:
                    err_msg = f"{tc.name} failed: {result.error or 'Execution error'}"
                    emit("TOOL_FAILED", {
                        "type": "tool_failed",
                        "tool": tc.name,
                        "status": "failed",
                        "message": err_msg,
                        "success": False,
                        "execution_time_ms": result.execution_time_ms,
                        "iteration": state.iteration_count,
                        "metadata": {"error": result.error},
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
                emit("AGENT_MAX_ITERATIONS", {
                    "max": state.max_iterations,
                })
                break

        # === BUILD RESULT ===
        elapsed = state.elapsed_seconds
        emit("AGENT_COMPLETED", {
            "type": "agent_completed",
            "status": "completed",
            "message": "Request completed.",
            "execution_id": state.execution_id,
            "iterations": state.iteration_count,
            "tool_calls": len(state.tool_calls),
            "elapsed_seconds": elapsed,
        })

        answer = state.final_answer or state.error or "Agent execution failed without producing an answer."

        # Extract citations from tool results if available
        citations: list[dict[str, Any]] = []
        seen_chunks: set[tuple[str, str]] = set()
        for tr in state.tool_results:
            if tr.success and hasattr(tr.result, "chunks") and tr.result.chunks:
                for chunk in tr.result.chunks:
                    doc_id = getattr(chunk, "document_id", "")
                    chunk_id = getattr(chunk, "chunk_id", "")
                    key = (doc_id, chunk_id)
                    if key not in seen_chunks:
                        seen_chunks.add(key)
                        citations.append({
                            "document_id": doc_id,
                            "chunk_id": chunk_id,
                            "page_index": getattr(chunk, "page_index", 0) if getattr(chunk, "page_index", None) is not None else 0,
                            "source_text": getattr(chunk, "text", ""),
                        })

        logger.info(
            "Agent completed: execution_id=%s, iterations=%d, tools=%d, citations=%d, time=%.1fs",
            state.execution_id,
            state.iteration_count,
            len(state.tool_calls),
            len(citations),
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
            citations=citations,
            activities=state.activities,
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
