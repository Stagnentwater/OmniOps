"""Conversation-scoped image context service for multi-turn chat persistence.

Preserves visual observations, equipment tags, diagram relationships, and image
storage paths across multi-turn chat sessions without requiring repeated image
re-uploads and without polluting the global vector database (Qdrant) or Knowledge Graph (Neo4j).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from database.chat_repository import ChatRepository

logger = logging.getLogger(__name__)


@dataclass
class ImageContextRecord:
    """Persistent representation of an image attached within a conversation."""

    document_id: str
    filename: str
    storage_path: str
    classification: str = "DIAGRAM"
    extracted_summary: str = ""
    detected_equipment: list[str] = field(default_factory=list)
    detected_connections: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSONB storage in message metadata."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "storage_path": self.storage_path,
            "classification": self.classification,
            "extracted_summary": self.extracted_summary,
            "detected_equipment": self.detected_equipment,
            "detected_connections": self.detected_connections,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageContextRecord:
        """Deserialize from dictionary."""
        return cls(
            document_id=str(data.get("document_id", "")),
            filename=str(data.get("filename", "")),
            storage_path=str(data.get("storage_path", "")),
            classification=str(data.get("classification", "DIAGRAM")),
            extracted_summary=str(data.get("extracted_summary", "")),
            detected_equipment=list(data.get("detected_equipment", [])),
            detected_connections=list(data.get("detected_connections", [])),
            timestamp=str(data.get("timestamp", "")),
        )


class ConversationImageService:
    """Manages conversation-scoped persistence and resolution of image contexts."""

    def __init__(self, chat_repository: ChatRepository | None = None) -> None:
        self._chat_repo = chat_repository or ChatRepository()

    def record_image_context(
        self,
        session_id: str,
        context: ImageContextRecord,
        message_id: str | None = None,
    ) -> None:
        """Associate image context with a specific chat message or the session."""
        if not session_id:
            logger.warning("No session_id provided. Cannot persist conversation image context.")
            return

        # If a specific message_id is provided, we can update its metadata
        if message_id:
            try:
                import json
                ctx_dict = context.to_dict() if hasattr(context, "to_dict") else context
                with self._chat_repo._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE chat_messages
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                            WHERE message_id = %s
                            """,
                            (
                                json.dumps({"image_context": ctx_dict}),
                                message_id,
                            ),
                        )
                    conn.commit()
                doc_id = getattr(context, "document_id", "") or (ctx_dict.get("document_id") if isinstance(ctx_dict, dict) else "")
                logger.info("Updated message %s with image context for doc %s", message_id, doc_id)
                return
            except Exception as e:
                logger.warning("Failed to update message metadata with image context: %s", e)

    def get_active_image_context(
        self,
        session_id: str,
        limit_turns: int = 10,
    ) -> ImageContextRecord | None:
        """Resolve the most recent active image context in this chat session.

        Inspects recent message metadata in reverse chronological order.
        Strictly isolated to the specified session_id.
        """
        if not session_id:
            return None

        try:
            messages = self._chat_repo.get_recent_messages(session_id=session_id, limit=limit_turns)
            for msg in reversed(messages):
                metadata = getattr(msg, "metadata", {}) or {}
                if isinstance(metadata, dict) and "image_context" in metadata:
                    raw_ctx = metadata["image_context"]
                    if isinstance(raw_ctx, dict):
                        return ImageContextRecord.from_dict(raw_ctx)
                # Fallback to direct image_document_id metadata from initial upload
                if isinstance(metadata, dict) and "image_document_id" in metadata:
                    fn = metadata.get("image_filename", "attached_image.png")
                    doc_id = metadata.get("image_document_id", "")
                    return ImageContextRecord(
                        document_id=doc_id,
                        filename=fn,
                        storage_path=metadata.get("image_url", ""),
                        classification="DIAGRAM" if any(k in fn.lower() for k in ["pid", "p&id", "diagram"]) else "PHOTOGRAPH",
                        extracted_summary=f"Attached image {fn}",
                    )
        except Exception as e:
            logger.warning("Failed to resolve active image context for session %s: %s", session_id, e)

        return None

    def build_prompt_context(self, context: ImageContextRecord) -> str:
        """Format resolved image context into a concise prompt directive for the agent."""
        eq_str = ", ".join(context.detected_equipment) if context.detected_equipment else "None tagged"
        conn_str = "; ".join(context.detected_connections[:5]) if context.detected_connections else (context.extracted_summary or "None detailed")
        return (
            f"[Active Session Diagram/Image Context: '{context.filename}' (ID: {context.document_id[:8]}...)\n"
            f"Classification: {context.classification}\n"
            f"Storage Location: '{context.storage_path}'\n"
            f"Visible Equipment Tags: {eq_str}\n"
            f"Observations/Connections: {conn_str}\n"
            f"Note: This visual context is persistent across follow-up queries in this session. "
            f"You may reference these equipment tags and connections directly without requesting a re-upload.]"
        )
