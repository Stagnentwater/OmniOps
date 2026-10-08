"""Image-to-chat context injection service.

After the vision pipeline processes an image, this service saves the
extracted description as a system message in the active chat session.
This allows the user to ask follow-up questions about the image
using Llama 3.2 (which sees the description in conversation history).

The vision model is NOT needed for follow-ups — the text is stored
once and reused as conversation context.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from database.chat_repository import ChatRepository

logger = logging.getLogger(__name__)


def inject_image_context(
    *,
    session_id: str,
    filename: str,
    classification: str,
    extracted_text: str,
    image_uri: str,
    confidence: float = 0.8,
    chat_repository: ChatRepository | None = None,
) -> str | None:
    """Save vision-extracted text as a system message in the chat session.

    Args:
        session_id: The chat session where the image was uploaded.
        filename: Original image filename.
        classification: Image classification label (e.g., "PHOTOGRAPH").
        extracted_text: The vision model's text description.
        image_uri: Storage URI of the original image.
        confidence: Vision extraction confidence score.
        chat_repository: Optional injected repository; creates one if None.

    Returns:
        The message_id of the saved system message, or None if session_id
        is not provided.
    """
    if not session_id:
        logger.info("No session_id provided. Skipping chat context injection.")
        return None

    repo = chat_repository or ChatRepository()

    timestamp = datetime.now(timezone.utc).isoformat()
    content = (
        f"[Image Analysis: {filename}]\n"
        f"Classification: {classification}\n"
        f"Confidence: {confidence:.0%}\n\n"
        f"{extracted_text}\n\n"
        f"[Source: {image_uri} | Processed: {timestamp}]"
    )

    try:
        message_id = repo.add_message(
            session_id=session_id,
            role="system",
            content=content,
            citations=[
                {
                    "source": "vision",
                    "image_uri": image_uri,
                    "classification": classification,
                    "filename": filename,
                }
            ],
        )
        logger.info(
            "Injected image context into session %s (message_id=%s, file=%s)",
            session_id,
            message_id,
            filename,
        )
        return message_id
    except Exception as e:
        logger.error(
            "Failed to inject image context into session %s: %s",
            session_id,
            e,
        )
        return None
