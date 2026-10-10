import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import json
import asyncio
import time
import base64
from fastapi.responses import StreamingResponse
from utils.event_bus import bus

from dependencies import (
    get_query_orchestrator, 
    get_agent_orchestrator,
    get_current_user,
    get_user_repo,
)
from database.chat_repository import ChatRepository
from database.user_repository import UserRepository, User
from generation.persona_builder import PersonaContextBuilder
from query.orchestrator import QueryOrchestrator
from agents.orchestrator import AgentOrchestrator
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])

class QueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    session_id: Optional[str] = None
    use_agent: Optional[bool] = None
    image_base64: Optional[str] = None
    image_filename: Optional[str] = None

class CitationItem(BaseModel):
    document_id: str
    chunk_id: str
    page_index: int
    source_text: str

class QueryResponse(BaseModel):
    answer: str
    citations: List[CitationItem]
    metadata: Dict[str, Any]


def _process_attached_image(image_base64: str, image_filename: Optional[str] = None) -> tuple[str, str, str]:
    """Decode and store image in StorageService and register in MetadataRepository.
    
    Returns:
        (document_id, local_file_path, storage_url)
    """
    from hashlib import sha256
    import os
    from storage.factory import get_storage_service
    from database.repositories import MetadataRepository, DocumentMetadata

    clean_b64 = image_base64
    if "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]

    image_bytes = base64.b64decode(clean_b64)
    doc_id = sha256(image_bytes).hexdigest()
    fn = image_filename or f"image_{doc_id[:8]}.png"
    ext = os.path.splitext(fn)[1].lower() or ".png"
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    content_type = mime_types.get(ext, "image/png")

    storage = get_storage_service()
    stored_obj = storage.put_bytes(
        document_id=doc_id,
        file_name=fn,
        content_type=content_type,
        data=image_bytes,
    )

    settings = get_settings()
    local_path = os.path.abspath(os.path.join(settings.storage.local_root, stored_obj.storage_key))

    try:
        repo = MetadataRepository()
        repo.save_document_metadata(
            DocumentMetadata(
                document_id=doc_id,
                file_name=fn,
                content_type=content_type,
                stored_object=stored_obj,
            )
        )
    except Exception as e:
        logger.warning("Could not persist document metadata for chat image: %s", e)

    storage_url = f"/documents/{doc_id}/content"
    return doc_id, local_path, storage_url


@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    agent_orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    legacy_orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
    user_repo: UserRepository = Depends(get_user_repo),
) -> QueryResponse:
    """Execute end-to-end Retrieval and Generation (agent or legacy)."""
    settings = get_settings()
    use_agent = (
        request.use_agent
        if request.use_agent is not None
        else settings.agent.enabled
    )

    image_metadata = None
    stored_path = None
    agent_query = request.query
    if request.image_base64:
        doc_id, stored_path, storage_url = _process_attached_image(
            request.image_base64, request.image_filename
        )
        fn = request.image_filename or f"image_{doc_id[:8]}.png"
        image_metadata = {
            "image_filename": fn,
            "image_document_id": doc_id,
            "image_url": storage_url,
            "image_base64": request.image_base64,
        }
        is_diagram = any(k in (request.query or "").lower() for k in ["p&id", "pid", "diagram", "schematic", "piping", "pfd", "flow sheet"]) or any(k in fn.lower() for k in ["p&id", "pid", "diagram", "schematic", "pfd"])
        rec_tool = "analyze_pid" if is_diagram else "analyze_image"
        agent_query = (
            f"[Attached Image: '{fn}' located at '{stored_path}'. "
            f"You MUST invoke {rec_tool} (or analyze_image) with image_path='{stored_path}' before answering. "
            f"Do not guess or output generic safety disclaimers without inspecting the image first. "
            f"Once visual tool findings return: "
            f"1. Directly explain what is shown: walk through equipment tags, valves, piping, instrumentation, and process flow in detail. "
            f"2. Include relevant operational safety notes as secondary guidance, but never replace or omit the diagram explanation. "
            f"3. If the image is a general, cartoon, or non-refinery image, explain what is depicted and state that it is not part of the refinery so questions based on it cannot be answered in an operational context].\n\n{request.query}"
        )

    persona_instructions = None
    if isinstance(current_user, User):
        user_profile = user_repo.get_profile(current_user.user_id)
        persona_instructions = PersonaContextBuilder.build(user_profile)
    else:
        persona_instructions = PersonaContextBuilder.build(None)

    if not use_agent:
        if stored_path and request.image_base64:
            try:
                from generation.vision_provider import VisionProvider
                from services.image_chat_service import inject_image_context
                vision_provider = VisionProvider(
                    base_url=settings.vision.ollama_base_url,
                    model=settings.vision.model_name,
                )
                raw_bytes = base64.b64decode(request.image_base64.split(",", 1)[-1])
                classification = vision_provider.classify_image(raw_bytes)
                desc = vision_provider.describe_image(raw_bytes)
                inject_image_context(
                    session_id=request.session_id or "",
                    filename=image_metadata["image_filename"] if image_metadata else "image.png",
                    classification=classification,
                    extracted_text=desc.text,
                    image_uri=f"file://{stored_path}",
                    chat_repository=ChatRepository(),
                )
            except Exception as vision_err:
                logger.warning("Failed non-agent vision analysis: %s", vision_err)

        result = legacy_orchestrator.answer_query(
            request.query,
            session_id=request.session_id,
            persona_instructions=persona_instructions,
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
            metadata=image_metadata,
        )

    agent_result = agent_orchestrator.run(
        query=agent_query,
        conversation_id=session_id or "",
        exclude_message_id=user_message_id,
        persona_instructions=persona_instructions,
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
    current_user: User = Depends(get_current_user),
    agent_orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    legacy_orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
    user_repo: UserRepository = Depends(get_user_repo),
):
    """Execute end-to-end Retrieval and Generation with SSE streaming."""
    settings = get_settings()
    use_agent = (
        request.use_agent
        if request.use_agent is not None
        else settings.agent.enabled
    )

    image_metadata = None
    stored_path = None
    agent_query = request.query
    if request.image_base64:
        doc_id, stored_path, storage_url = _process_attached_image(
            request.image_base64, request.image_filename
        )
        fn = request.image_filename or f"image_{doc_id[:8]}.png"
        image_metadata = {
            "image_filename": fn,
            "image_document_id": doc_id,
            "image_url": storage_url,
            "image_base64": request.image_base64,
        }
        is_diagram = any(k in (request.query or "").lower() for k in ["p&id", "pid", "diagram", "schematic", "piping", "pfd", "flow sheet"]) or any(k in fn.lower() for k in ["p&id", "pid", "diagram", "schematic", "pfd"])
        rec_tool = "analyze_pid" if is_diagram else "analyze_image"
        agent_query = (
            f"[Attached Image: '{fn}' located at '{stored_path}'. "
            f"You MUST invoke {rec_tool} (or analyze_image) with image_path='{stored_path}' before answering. "
            f"Do not guess or output generic safety disclaimers without inspecting the image first. "
            f"Once visual tool findings return: "
            f"1. Directly explain what is shown: walk through equipment tags, valves, piping, instrumentation, and process flow in detail. "
            f"2. Include relevant operational safety notes as secondary guidance, but never replace or omit the diagram explanation. "
            f"3. If the image is a general, cartoon, or non-refinery image, explain what is depicted and state that it is not part of the refinery so questions based on it cannot be answered in an operational context].\n\n{request.query}"
        )

    chat_repo = ChatRepository()
    session_id = request.session_id
    if not session_id:
        user_id = current_user.user_id if isinstance(current_user, User) else None
        session_id = chat_repo.create_session(user_id=user_id)

    user_message_id = chat_repo.add_message(
        session_id=session_id,
        role="user",
        content=request.query,
        metadata=image_metadata,
    )

    persona_instructions = None
    if isinstance(current_user, User):
        user_profile = user_repo.get_profile(current_user.user_id)
        persona_instructions = PersonaContextBuilder.build(user_profile)
    else:
        persona_instructions = PersonaContextBuilder.build(None)

    def run_query():
        try:
            if not use_agent:
                if stored_path and request.image_base64:
                    try:
                        from generation.vision_provider import VisionProvider
                        from services.image_chat_service import inject_image_context
                        vision_provider = VisionProvider(
                            base_url=settings.vision.ollama_base_url,
                            model=settings.vision.model_name,
                        )
                        raw_bytes = base64.b64decode(request.image_base64.split(",", 1)[-1])
                        classification = vision_provider.classify_image(raw_bytes)
                        desc = vision_provider.describe_image(raw_bytes)
                        inject_image_context(
                            session_id=session_id,
                            filename=image_metadata["image_filename"] if image_metadata else "image.png",
                            classification=classification,
                            extracted_text=desc.text,
                            image_uri=f"file://{stored_path}",
                            chat_repository=chat_repo,
                        )
                    except Exception as vision_err:
                        logger.warning("Failed non-agent vision analysis in stream: %s", vision_err)

                legacy_orchestrator.answer_query(
                    request.query,
                    session_id=session_id,
                    history_exclude_message_id=user_message_id,
                    persona_instructions=persona_instructions,
                )
            else:
                def emit_to_bus(stage: str, data: dict):
                    event = {"stage": stage, "timestamp": time.time()}
                    if data:
                        event.update(data)
                    bus.publish(f"query_{session_id}", event)

                agent_result = agent_orchestrator.run(
                    query=agent_query,
                    conversation_id=session_id,
                    exclude_message_id=user_message_id,
                    on_event=emit_to_bus,
                    persona_instructions=persona_instructions,
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

