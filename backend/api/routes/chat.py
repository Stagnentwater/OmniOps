"""API routes for Chat Sessions with user ownership enforcement."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from database.chat_repository import ChatRepository
from database.user_repository import User
from dependencies import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_repo() -> ChatRepository:
    return ChatRepository()


@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
) -> list[dict[str, Any]]:
    """List chat sessions owned by the authenticated user."""
    sessions = repo.list_sessions(user_id=current_user.user_id)
    return [
        {
            "id": s.session_id,
            "title": s.title,
            "user_id": s.user_id,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.post("/sessions")
def create_session(
    current_user: User = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
) -> dict[str, str]:
    """Create a new chat session owned by the authenticated user."""
    session_id = repo.create_session(user_id=current_user.user_id)
    return {"session_id": session_id}


@router.get("/sessions/{session_id}")
def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
) -> list[dict[str, Any]]:
    """Fetch messages for a session after verifying ownership."""
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found",
        )
    if session.user_id and session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have access to this chat session",
        )
    messages = repo.get_messages(session_id)
    return [
        {
            "id": m.message_id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations,
            "metadata": getattr(m, "metadata", {}) or {},
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    repo: ChatRepository = Depends(get_chat_repo),
) -> dict[str, str]:
    """Delete a chat session after verifying ownership."""
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found",
        )
    if session.user_id and session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to delete this chat session",
        )
    repo.delete_session(session_id, user_id=current_user.user_id)
    return {"status": "deleted"}
