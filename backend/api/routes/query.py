from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from dependencies import get_query_orchestrator
from query.orchestrator import QueryOrchestrator

router = APIRouter(prefix="/query", tags=["Query"])

class QueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None

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
