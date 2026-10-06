"""Unit tests for multi-turn query orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from database.chat_repository import ChatMessage
from generation.generation_models import GeneratedAnswer, GenerationResult, RawGeneration
from query.orchestrator import QueryOrchestrator
from retrieval.retrieval_models import RetrievalContext, RetrievedChunk


class FakeRetrievalService:
    """Records retrieval calls and returns fixed, citable evidence."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, int]] = []

    def retrieve(self, query: str, limit: int) -> RetrievalContext:
        self.queries.append((query, limit))
        return RetrievalContext(
            query=query,
            chunks=(
                RetrievedChunk(
                    chunk_id="chunk-1",
                    document_id="document-1",
                    text="Evidence for the current query.",
                    score=0.9,
                    page_index=1,
                    section=None,
                    metadata={},
                ),
            ),
            entities=(),
            relationships=(),
        )


class CapturingGenerationService:
    """Captures conversational context without invoking an LLM."""

    def __init__(self) -> None:
        self.histories: list[tuple] = []

    def generate_answer(self, context, conversation_history=()) -> GenerationResult:
        self.histories.append(tuple(conversation_history))
        return GenerationResult(
            answer=GeneratedAnswer(answer_text="Answer. [Context #1]", citations=()),
            raw=RawGeneration(raw_response="Answer. [Context #1]", metadata={}),
        )


class FakeChatRepository:
    """In-memory chat history fake with repository-compatible semantics."""

    def __init__(self, messages: list[ChatMessage]) -> None:
        self.messages = messages
        self.calls: list[tuple[str, int, str | None]] = []

    def get_recent_messages(
        self,
        session_id: str,
        limit: int,
        exclude_message_id: str | None = None,
    ) -> list[ChatMessage]:
        self.calls.append((session_id, limit, exclude_message_id))
        messages = [
            message
            for message in self.messages
            if message.session_id == session_id and message.message_id != exclude_message_id
        ]
        return messages[-limit:]


def make_message(
    message_id: str,
    session_id: str,
    role: str,
    content: str,
) -> ChatMessage:
    """Build a deterministic chat message for a repository fake."""
    return ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        citations=[],
        created_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
    )


class TestQueryOrchestratorConversationHistory(unittest.TestCase):
    def setUp(self) -> None:
        self.retrieval_service = FakeRetrievalService()
        self.generation_service = CapturingGenerationService()
        self.chat_repository = FakeChatRepository(
            [
                make_message("message-1", "session-1", "user", "Tell me about Pump P-301."),
                make_message("message-2", "session-1", "assistant", "It is in Area A."),
                make_message("message-3", "session-1", "user", "What maintenance is required?"),
            ]
        )
        self.orchestrator = QueryOrchestrator(
            retrieval_service=self.retrieval_service,
            generation_service=self.generation_service,
            chat_repository=self.chat_repository,
            conversation_history_limit=2,
        )

    def test_uses_bounded_prior_turns_and_excludes_current_message(self) -> None:
        self.orchestrator.answer_query(
            "What maintenance is required?",
            session_id="session-1",
            history_exclude_message_id="message-3",
        )

        self.assertEqual(
            self.chat_repository.calls,
            [("session-1", 2, "message-3")],
        )
        history = self.generation_service.histories[0]
        self.assertEqual([turn.role for turn in history], ["user", "assistant"])
        self.assertEqual(
            [turn.content for turn in history],
            ["Tell me about Pump P-301.", "It is in Area A."],
        )

    def test_query_without_configured_history_preserves_existing_behavior(self) -> None:
        orchestrator = QueryOrchestrator(
            retrieval_service=self.retrieval_service,
            generation_service=self.generation_service,
        )

        orchestrator.answer_query("What maintenance is required?")

        self.assertEqual(self.generation_service.histories[-1], ())


if __name__ == "__main__":
    unittest.main()
