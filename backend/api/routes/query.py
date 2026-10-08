from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import json
import asyncio
import time
from fastapi.responses import StreamingResponse
from utils.event_bus import bus

from dependencies import get_query_orchestrator, get_agent_orchestrator
from database.chat_repository import ChatRepository
from query.orchestrator import QueryOrchestrator
from agents.orchestrator import AgentOrchestrator
from config.settings import get_settings

router = APIRouter(prefix="/query", tags=["Query"])

class QueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    session_id: Optional[str] = None
    use_agent: Optional[bool] = None

class CitationItem(BaseModel):
    document_id: str
    chunk_id: str
    page_index: int
    source_text: str

class QueryResponse(BaseModel):
    answer: str
    citations: List[CitationItem]
    metadata: Dict[str, Any]

@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    agent_orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    legacy_orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
) -> QueryResponse:
    """Execute end-to-end Retrieval and Generation (agent or legacy)."""
    settings = get_settings()
    use_agent = (
        request.use_agent
        if request.use_agent is not None
        else settings.agent.enabled
    )

    if not use_agent:
        result = legacy_orchestrator.answer_query(
            request.query,
            session_id=request.session_id,
        )
        citations = [
            CitationItem(
                document_id=c.document_id,
                chunk_id=c.chunk_id,
                page_index=c.page_index,
                source_text=c.source_text,
            )
            for c in result.answer.citations
        ]
        return QueryResponse(
            answer=result.answer.answer_text,
            citations=citations,
            metadata=result.raw.metadata or {},
        )

    # Agentic execution with conversation memory
    chat_repo = ChatRepository()
    session_id = request.session_id
    user_message_id = None
    if session_id:
        user_message_id = chat_repo.add_message(
            session_id=session_id,
            role="user",
            content=request.query,
        )

    agent_result = agent_orchestrator.run(
        query=request.query,
        conversation_id=session_id or "",
        exclude_message_id=user_message_id,
    )

    citations = [
        CitationItem(
            document_id=c.get("document_id", ""),
            chunk_id=c.get("chunk_id", ""),
            page_index=c.get("page_index", 0),
            source_text=c.get("source_text", ""),
        )
        for c in agent_result.citations
    ]

    metadata = {
        "iterations": agent_result.iterations,
        "tool_calls": agent_result.tool_calls_made,
        "activities": getattr(agent_result, "activities", []),
        "execution_time_seconds": agent_result.execution_time_seconds,
    }
    if agent_result.error:
        metadata["error"] = agent_result.error

    if session_id:
        chat_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=agent_result.answer,
            citations=[
                c.model_dump() if hasattr(c, "model_dump") else c.dict()
                for c in citations
            ],
            metadata=metadata,
        )

    return QueryResponse(
        answer=agent_result.answer,
        citations=citations,
        metadata=metadata,
    )

@router.post("/stream")
async def stream_query(
    request: QueryRequest,
    agent_orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    legacy_orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
):
    """Execute end-to-end Retrieval and Generation with SSE streaming."""
    settings = get_settings()
    use_agent = (
        request.use_agent
        if request.use_agent is not None
        else settings.agent.enabled
    )

    chat_repo = ChatRepository()
    session_id = request.session_id
    if not session_id:
        session_id = chat_repo.create_session()

    user_message_id = chat_repo.add_message(
        session_id=session_id,
        role="user",
        content=request.query,
    )

    def run_query():
        try:
            if not use_agent:
                legacy_orchestrator.answer_query(
                    request.query,
                    session_id=session_id,
                    history_exclude_message_id=user_message_id,
                )
            else:
                def emit_to_bus(stage: str, data: dict):
                    event = {"stage": stage, "timestamp": time.time()}
                    if data:
                        event.update(data)
                    bus.publish(f"query_{session_id}", event)

                agent_result = agent_orchestrator.run(
                    query=request.query,
                    conversation_id=session_id,
                    exclude_message_id=user_message_id,
                    on_event=emit_to_bus,
                )

                metadata = {
                    "iterations": agent_result.iterations,
                    "tool_calls": agent_result.tool_calls_made,
                    "activities": getattr(agent_result, "activities", []),
                    "execution_time_seconds": agent_result.execution_time_seconds,
                    "error": agent_result.error,
                }

                bus.publish(
                    f"query_{session_id}",
                    {
                        "stage": "COMPLETED",
                        "type": "agent_completed",
                        "status": "completed",
                        "timestamp": time.time(),
                        "result": {
                            "answer": agent_result.answer,
                            "citations": agent_result.citations,
                            "metadata": metadata,
                        },
                    },
                )
        except Exception as e:
            bus.publish(
                f"query_{session_id}",
                {
                    "stage": "FAILED",
                    "type": "agent_error",
                    "status": "failed",
                    "timestamp": time.time(),
                    "error": str(e),
                },
            )

    from starlette.concurrency import run_in_threadpool
    asyncio.create_task(run_in_threadpool(run_query))

    async def event_generator():
        topic = f"query_{session_id}"
        queue = bus.subscribe(topic)
        try:
            yield f"data: {json.dumps({'stage': 'SESSION_INFO', 'session_id': session_id})}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("stage") == "COMPLETED":
                    result = event.get("result", {})
                    chat_repo = ChatRepository()
                    chat_repo.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=result.get("answer", ""),
                        citations=result.get("citations", []),
                        metadata=result.get("metadata", {}),
                    )
                    break
                elif event.get("stage") == "FAILED":
                    break
        finally:
            bus.unsubscribe(topic, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

