"""Query pipeline orchestrator."""

from __future__ import annotations
import logging
import time

from database.chat_repository import ChatRepository
from generation.generation_models import ConversationTurn, GenerationResult
from generation.service import GenerationService
from retrieval.service import RetrievalService
from utils.event_bus import bus

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """Coordinates the Retrieval and Generation stages for user queries.
    
    Instantiates NO infrastructure. Dependencies are injected.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        generation_service: GenerationService,
        chat_repository: ChatRepository | None = None,
        conversation_history_limit: int | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._generation_service = generation_service
        self._chat_repository = chat_repository
        self._conversation_history_limit = conversation_history_limit

    def answer_query(
        self,
        query: str,
        limit: int = 5,
        session_id: str | None = None,
        history_exclude_message_id: str | None = None,
    ) -> GenerationResult:
        """Execute the end-to-end read path."""
        def emit(stage: str, data: dict | None = None):
            if session_id:
                event = {"stage": stage, "timestamp": time.time()}
                if data:
                    event.update(data)
                bus.publish(f"query_{session_id}", event)

        try:
            emit("GENERATING_EMBEDDING")
            logger.info(f"Query Started: '{query}'")
            
            # 1. Retrieve deterministic context (Vector + Graph)
            emit("SEARCHING_VECTOR_DB")
            emit("EXPANDING_KNOWLEDGE_GRAPH")
            context = self._retrieval_service.retrieve(query, limit=limit)
            
            emit("RETRIEVED_CONTEXT", {
                "chunks": len(context.chunks), 
                "entities": len(context.entities),
                "relationships": len(context.relationships),
                "metadata": {
                    "retrieved_chunks": [
                        {
                            "id": c.chunk_id,
                            "document_id": c.document_id,
                            "text": c.text,
                            "score": c.score
                        } for c in context.chunks
                    ],
                    "retrieved_entities": [
                        {
                            "id": e.entity_id,
                            "name": e.canonical_name,
                            "type": e.entity_type
                        } for e in context.entities
                    ],
                    "retrieved_relationships": [
                        {
                            "source": r.source_id,
                            "target": r.target_id,
                            "type": r.relationship_type
                        } for r in context.relationships
                    ]
                }
            })
            logger.info(f"Retrieval Complete: {len(context.chunks)} chunks, {len(context.entities)} entities.")

            conversation_history = self._load_conversation_history(
                session_id=session_id,
                exclude_message_id=history_exclude_message_id,
            )
            
            emit("BUILDING_PROMPT")
            emit("GENERATING_RESPONSE")
            # 2. Generate reasoned answer strictly from context
            result = self._generation_service.generate_answer(
                context,
                conversation_history=conversation_history,
            )
            emit("VALIDATING_CITATIONS")
            logger.info("Generation Complete.")
            
            emit("COMPLETED", {"result": {
                "answer": result.answer.answer_text,
                "citations": [
                    {
                        "document_id": c.document_id,
                        "chunk_id": c.chunk_id,
                        "page_index": c.page_index,
                        "source_text": c.source_text
                    } for c in result.answer.citations
                ],
                "metadata": {
                    "latency": getattr(result.raw, "latency", 0),
                    "model": getattr(result.raw, "model", "unknown"),
                    "retrieved_chunks": [
                        {
                            "id": c.chunk_id,
                            "document_id": c.document_id,
                            "text": c.text,
                            "score": c.score
                        } for c in context.chunks
                    ],
                    "retrieved_entities": [
                        {
                            "id": e.entity_id,
                            "name": e.canonical_name,
                            "type": e.entity_type
                        } for e in context.entities
                    ],
                    "retrieved_relationships": [
                        {
                            "source": r.source_id,
                            "target": r.target_id,
                            "type": r.relationship_type
                        } for r in context.relationships
                    ]
                }
            }})
            return result
            
        except Exception as e:
            logger.error(f"Query Pipeline failed: {e}")
            emit("FAILED", {"error": str(e)})
            raise

    def _load_conversation_history(
        self,
        session_id: str | None,
        exclude_message_id: str | None,
    ) -> tuple[ConversationTurn, ...]:
        """Load safe, bounded prior turns without making them retrievable evidence."""
        if (
            session_id is None
            or self._chat_repository is None
            or self._conversation_history_limit is None
        ):
            return ()

        messages = self._chat_repository.get_recent_messages(
            session_id=session_id,
            limit=self._conversation_history_limit,
            exclude_message_id=exclude_message_id,
        )
        turns: list[ConversationTurn] = []
        for message in messages:
            if message.role not in {"user", "assistant"}:
                logger.warning(
                    "Skipping unsupported role in conversation history for session %s.",
                    session_id,
                )
                continue
            if not message.content.strip():
                continue
            turns.append(ConversationTurn(role=message.role, content=message.content))

        return tuple(turns)
