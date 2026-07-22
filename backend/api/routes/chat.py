"""API routes for Chat Sessions."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from datetime import datetime

from database.chat_repository import ChatRepository

router = APIRouter(prefix="/chat", tags=["chat"])

def get_chat_repo() -> ChatRepository:
    return ChatRepository()

@router.get("/sessions")
def list_sessions(repo: ChatRepository = Depends(get_chat_repo)) -> list[dict[str, Any]]:
    sessions = repo.list_sessions()
    return [
        {
            "id": s.session_id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]

@router.post("/sessions")
def create_session(repo: ChatRepository = Depends(get_chat_repo)) -> dict[str, str]:
    session_id = repo.create_session()
    return {"session_id": session_id}

@router.get("/sessions/{session_id}")
def get_session_messages(session_id: str, repo: ChatRepository = Depends(get_chat_repo)) -> list[dict[str, Any]]:
    messages = repo.get_messages(session_id)
    return [
        {
            "id": m.message_id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, repo: ChatRepository = Depends(get_chat_repo)) -> dict[str, str]:
    repo.delete_session(session_id)
    return {"status": "deleted"}
