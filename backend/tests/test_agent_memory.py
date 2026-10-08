"""Tests for Agent Conversation Memory (AGENT-MEMORY-001).

Validates:
1. Agent receives prior conversation context
2. Cross-turn references resolved across multi-turn interactions
3. Context limits (max_history_turns) respected and bounded
4. ChatRepository integration with message exclusion
5. Citation extraction and propagation to AgentResult
6. Query route integration with conversation memory
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from agents.ollama_agent_provider import (
    OllamaAgentProvider,
    OllamaChatResponse,
    OllamaToolCall,
)
from agents.orchestrator import AgentOrchestrator, AgentResult
from agents.tool_executor import ToolExecutor
from agents.tool_interface import Tool, ToolDefinition, ToolResult
from agents.tool_registry import ToolRegistry
from agents.tools.calculate import CalculateTool
from agents.tools.search_documents import SearchDocumentsResult, SearchDocumentsTool
from calculation.service import CalculationService
from calculation.validator import CodeValidator
from database.chat_repository import ChatMessage
from retrieval.retrieval_models import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers and Fakes
# ---------------------------------------------------------------------------

class FakeSubprocessSandbox:
    def name(self) -> str:
        return "fake_subprocess"

    def execute(self, code: str, inputs: dict[str, Any] | None = None, timeout_seconds: float = 5.0):
        sandbox_globals: dict[str, Any] = {}
        sandbox_locals: dict[str, Any] = {}
        exec(code, sandbox_globals, sandbox_locals)
        output = sandbox_locals.get("result", "")
        return MagicMock(
            success=True,
            output=str(output),
            exit_code=0,
            execution_time_ms=10.0,
            error=None,
        )


class FakeChatRepository:
    """In-memory chat repository fake."""

    def __init__(self, messages: list[ChatMessage] | None = None) -> None:
        self.messages: list[ChatMessage] = messages or []
        self.get_recent_calls: list[tuple[str, int, str | None]] = []
        self.added_messages: list[tuple[str, str, str]] = []

    def get_recent_messages(
        self,
        session_id: str,
        limit: int,
        exclude_message_id: str | None = None,
    ) -> list[ChatMessage]:
        self.get_recent_calls.append((session_id, limit, exclude_message_id))
        matching = [
            m for m in self.messages
            if m.session_id == session_id and m.message_id != exclude_message_id
        ]
        return matching[-limit:]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> str:
        msg_id = f"msg-{len(self.messages) + 1}"
        msg = ChatMessage(
            message_id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            citations=citations or [],
            created_at=datetime.now(timezone.utc),
        )
        self.messages.append(msg)
        self.added_messages.append((session_id, role, content))
        return msg_id


def make_chat_message(
    msg_id: str,
    session_id: str,
    role: str,
    content: str,
) -> ChatMessage:
    return ChatMessage(
        message_id=msg_id,
        session_id=session_id,
        role=role,
        content=content,
        citations=[],
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestAgentMemoryPriorContext(unittest.TestCase):
    """Test: Agent receives prior conversation context passed via conversation_history."""

    def test_agent_includes_prior_history_in_llm_messages(self) -> None:
        captured_messages: list[list[dict[str, Any]]] = []

        def fake_chat(messages, tools=None):
            captured_messages.append(list(messages))
            return OllamaChatResponse(content="Sure, P-101 runs at 25 bar.")

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = fake_chat

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_history_turns=10,
        )

        history = [
            {"role": "user", "content": "What pump is in Unit 200?"},
            {"role": "assistant", "content": "Pump P-101 is located in Unit 200."},
        ]

        result = orchestrator.run(
            query="What is its operating pressure?",
            conversation_history=history,
        )

        self.assertEqual(result.answer, "Sure, P-101 runs at 25 bar.")
        self.assertEqual(len(captured_messages), 1)
        messages = captured_messages[0]

        # Structure should be: system prompt, history turn 1, history turn 2, current user query
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], {"role": "user", "content": "What pump is in Unit 200?"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "Pump P-101 is located in Unit 200."})
        self.assertEqual(messages[3], {"role": "user", "content": "What is its operating pressure?"})


class TestAgentMemoryChatRepository(unittest.TestCase):
    """Test: Agent automatically loads conversation history from ChatRepository."""

    def test_loads_history_from_chat_repository(self) -> None:
        chat_repo = FakeChatRepository([
            make_chat_message("m1", "sess-100", "user", "Who is the lead operator?"),
            make_chat_message("m2", "sess-100", "assistant", "The lead operator is Jane Doe."),
            make_chat_message("m3", "sess-100", "user", "What shift does she work?"),
        ])

        captured_messages: list[list[dict[str, Any]]] = []

        def fake_chat(messages, tools=None):
            captured_messages.append(list(messages))
            return OllamaChatResponse(content="She works the night shift.")

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = fake_chat

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            chat_repository=chat_repo,
            max_history_turns=5,
        )

        result = orchestrator.run(
            query="What shift does she work?",
            conversation_id="sess-100",
            exclude_message_id="m3",
        )

        self.assertEqual(result.answer, "She works the night shift.")
        # Verify repository called with exclude_message_id="m3"
        self.assertEqual(chat_repo.get_recent_calls, [("sess-100", 5, "m3")])

        messages = captured_messages[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], {"role": "user", "content": "Who is the lead operator?"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "The lead operator is Jane Doe."})
        self.assertEqual(messages[3], {"role": "user", "content": "What shift does she work?"})


class TestAgentMemoryContextLimits(unittest.TestCase):
    """Test: Context limits (max_history_turns) are strictly respected."""

    def test_history_is_bounded_to_max_history_turns(self) -> None:
        # Create 10 turns of history
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(10)
        ]

        captured_messages: list[list[dict[str, Any]]] = []

        def fake_chat(messages, tools=None):
            captured_messages.append(list(messages))
            return OllamaChatResponse(content="Acknowledged.")

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = fake_chat

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
            max_history_turns=4,  # limit to only the 4 most recent turns
        )

        orchestrator.run(
            query="Current question",
            conversation_history=history,
        )

        messages = captured_messages[0]
        # system (1) + bounded history (4) + user query (1) = 6 messages
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["content"], "Message 6")
        self.assertEqual(messages[2]["content"], "Message 7")
        self.assertEqual(messages[3]["content"], "Message 8")
        self.assertEqual(messages[4]["content"], "Message 9")
        self.assertEqual(messages[5]["content"], "Current question")


class TestAgentMemoryCrossTurnResolution(unittest.TestCase):
    """Test: Resolves cross-turn references (e.g. pronoun/reference -> tool call)."""

    def test_cross_turn_reference_triggers_calculation(self) -> None:
        """Turn 1 mentions 25 bar. Turn 2 asks to convert 'its pressure' to psi."""
        history = [
            {"role": "user", "content": "What is the design pressure of pump P-101?"},
            {
                "role": "assistant",
                "content": "According to data sheet DS-P101, Pump P-101 has a design pressure of 25.0 bar.",
            },
        ]

        # Iteration 1: LLM sees context about 25.0 bar and calls calculate(expression="25.0 * 14.5038")
        # Iteration 2: LLM receives calculation result and answers
        call_seq = [
            OllamaChatResponse(
                content="I will convert the 25.0 bar design pressure from the previous turn into psi.",
                tool_calls=[
                    OllamaToolCall(
                        name="calculate",
                        arguments={"expression": "25.0 * 14.5038"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="The design pressure of 25.0 bar converts to 362.6 psi.",
            ),
        ]

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = call_seq

        calc_service = CalculationService(
            sandbox=FakeSubprocessSandbox(),
            validator=CodeValidator(),
            timeout_seconds=5.0,
        )
        calc_tool = CalculateTool(calc_service)

        registry = ToolRegistry()
        registry.register(calc_tool)
        executor = ToolExecutor(registry)

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
        )

        result = orchestrator.run(
            query="Convert its design pressure to psi.",
            conversation_history=history,
        )

        self.assertIn("362.6 psi", result.answer)
        self.assertEqual(len(result.tool_calls_made), 1)
        self.assertEqual(result.tool_calls_made[0]["tool"], "calculate")
        self.assertEqual(
            result.tool_calls_made[0]["arguments"],
            {"expression": "25.0 * 14.5038"},
        )


class TestAgentMemoryCitations(unittest.TestCase):
    """Test: Tool execution results with chunks populate AgentResult.citations."""

    def test_search_documents_populates_citations(self) -> None:
        mock_retrieval = MagicMock()
        mock_retrieval._retrieve_vectors.return_value = [
            RetrievedChunk(
                chunk_id="chunk-abc",
                document_id="SOP-502.pdf",
                text="Normal reactor temperature is 450 C.",
                score=0.92,
                page_index=14,
                section="Section 4.1",
                metadata={},
            )
        ]

        search_tool = SearchDocumentsTool(mock_retrieval)
        registry = ToolRegistry()
        registry.register(search_tool)
        executor = ToolExecutor(registry)

        call_seq = [
            OllamaChatResponse(
                content=None,
                tool_calls=[
                    OllamaToolCall(
                        name="search_documents",
                        arguments={"query": "reactor operating temperature"},
                    )
                ],
            ),
            OllamaChatResponse(
                content="The normal reactor operating temperature is 450 C as stated in SOP-502.pdf.",
            ),
        ]

        mock_llm = MagicMock(spec=OllamaAgentProvider)
        mock_llm.chat.side_effect = call_seq

        orchestrator = AgentOrchestrator(
            llm_provider=mock_llm,
            tool_registry=registry,
            tool_executor=executor,
        )

        result = orchestrator.run("What is the reactor operating temperature?")

        self.assertEqual(len(result.citations), 1)
        citation = result.citations[0]
        self.assertEqual(citation["document_id"], "SOP-502.pdf")
        self.assertEqual(citation["chunk_id"], "chunk-abc")
        self.assertEqual(citation["page_index"], 14)
        self.assertEqual(citation["source_text"], "Normal reactor temperature is 450 C.")


class TestAgentQueryRouteMemory(unittest.TestCase):
    """Test: FastAPI query route uses AgentOrchestrator with conversation memory."""

    def test_query_route_submit_with_agent(self) -> None:
        import asyncio
        from api.routes.query import QueryRequest, submit_query

        mock_agent_orchestrator = MagicMock(spec=AgentOrchestrator)
        mock_agent_orchestrator.run.return_value = AgentResult(
            answer="Unit 200 contains crude charge pump P-101.",
            tool_calls_made=[],
            iterations=1,
            execution_time_seconds=0.1,
            citations=[
                {
                    "document_id": "PND-200.pdf",
                    "chunk_id": "chk-1",
                    "page_index": 3,
                    "source_text": "P-101 in Unit 200",
                }
            ],
        )

        mock_legacy_orchestrator = MagicMock()

        request = QueryRequest(
            query="What pump is in Unit 200?",
            session_id=None,
            use_agent=True,
        )

        response = asyncio.run(
            submit_query(
                request=request,
                agent_orchestrator=mock_agent_orchestrator,
                legacy_orchestrator=mock_legacy_orchestrator,
            )
        )

        self.assertEqual(response.answer, "Unit 200 contains crude charge pump P-101.")
        self.assertEqual(len(response.citations), 1)
        self.assertEqual(response.citations[0].document_id, "PND-200.pdf")
        self.assertEqual(response.metadata["iterations"], 1)
        mock_agent_orchestrator.run.assert_called_once()
        mock_legacy_orchestrator.answer_query.assert_not_called()

    def test_query_route_submit_with_legacy_fallback(self) -> None:
        import asyncio
        from api.routes.query import QueryRequest, submit_query
        from generation.generation_models import GeneratedAnswer, GenerationResult, RawGeneration

        mock_agent_orchestrator = MagicMock(spec=AgentOrchestrator)
        mock_legacy_orchestrator = MagicMock()
        mock_legacy_orchestrator.answer_query.return_value = GenerationResult(
            answer=GeneratedAnswer(answer_text="Legacy RAG response", citations=()),
            raw=RawGeneration(raw_response="Legacy RAG response", metadata={}),
        )

        request = QueryRequest(
            query="What is the pressure?",
            use_agent=False,
        )

        response = asyncio.run(
            submit_query(
                request=request,
                agent_orchestrator=mock_agent_orchestrator,
                legacy_orchestrator=mock_legacy_orchestrator,
            )
        )

        self.assertEqual(response.answer, "Legacy RAG response")
        mock_legacy_orchestrator.answer_query.assert_called_once()
        mock_agent_orchestrator.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
