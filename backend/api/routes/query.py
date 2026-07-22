from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import json
import asyncio
from fastapi.responses import StreamingResponse
from utils.event_bus import bus

from dependencies import get_query_orchestrator
from database.chat_repository import ChatRepository
# pyrefly: ignore [missing-import]
from query.orchestrator import QueryOrchestrator

router = APIRouter(prefix="/query", tags=["Query"])

class QueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    session_id: Optional[str] = None

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
    orchestrator: QueryOrchestrator = Depends(get_query_orchestrator)
) -> QueryResponse:
    """Execute end-to-end Retrieval and Generation."""
    # Run the real query orchestrator
    result = orchestrator.answer_query(request.query)
    
    citations = [
        CitationItem(
            document_id=c.document_id,
            chunk_id=c.chunk_id,
            page_index=c.page_index,
            source_text=c.source_text
        )
        for c in result.answer.citations
    ]
    
    return QueryResponse(
        answer=result.answer.answer_text,
        citations=citations,
        metadata=result.raw.metadata or {}
    )

@router.post("/stream")
async def stream_query(
    request: QueryRequest,
    orchestrator: QueryOrchestrator = Depends(get_query_orchestrator)
):
    """Execute end-to-end Retrieval and Generation with SSE streaming."""
    chat_repo = ChatRepository()
    session_id = request.session_id
    if not session_id:
        session_id = chat_repo.create_session()
        
    chat_repo.add_message(session_id=session_id, role="user", content=request.query)
    
    def run_query():
        try:
            orchestrator.answer_query(request.query, session_id=session_id)
        except Exception:
            pass # Handled internally and FAILED event is emitted

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
                        citations=result.get("citations", [])
                    )
                    break
                elif event.get("stage") == "FAILED":
                    break
        finally:
            bus.unsubscribe(topic, queue)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
