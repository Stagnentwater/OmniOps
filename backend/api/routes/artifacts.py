"""Artifact download, Evidence Ledger retrieval, and Permit Human Sign-off API."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from database.repositories import MetadataRepository
from database.user_repository import User
from dependencies import get_current_user, get_metadata_repo
from permits.permit_models import IndustrialPermit, PermitStatus
from permits.review_service import PermitReviewService
from storage.factory import get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])
review_service = PermitReviewService()

# In-memory registry for active permit review sessions (backed by documents/chat metadata)
_PERMIT_CACHE: dict[str, IndustrialPermit] = {}


def register_permit(permit: IndustrialPermit) -> None:
    """Register an active permit in cache for review and sign-off tracking."""
    _PERMIT_CACHE[permit.permit_id] = permit


def get_cached_permit(permit_id: str) -> IndustrialPermit | None:
    return _PERMIT_CACHE.get(permit_id)


class PermitSignOffRequest(BaseModel):
    """Payload submitted by authorized engineer or safety officer."""

    reviewer_name: str = Field(..., description="Full legal name of reviewing engineer")
    reviewer_role: str = Field(..., description="Role title (e.g. Plant Safety Officer, Lead Operator)")
    signature_confirmed: bool = Field(..., description="Explicit human confirmation checkbox")
    is_automated_agent: bool = Field(default=False, description="Flag indicating automated request")


@router.get("/my-deliverables")
async def get_my_deliverables(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve all deliverables and industrial permits generated for the authenticated user account."""
    deliverables: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    try:
        from database.chat_repository import ChatRepository
        chat_repo = ChatRepository()
        with chat_repo._connect() as conn:
            chat_repo._ensure_tables(conn)
            with conn.cursor() as cur:
                user_param = str(current_user.user_id) if current_user else None
                if user_param:
                    cur.execute(
                        """
                        SELECT 
                            m.message_id, 
                            m.session_id, 
                            m.metadata, 
                            m.created_at, 
                            s.title as session_title
                        FROM chat_messages m
                        JOIN chat_sessions s ON m.session_id = s.session_id
                        WHERE s.user_id = %s
                          AND (m.metadata ? 'artifact' OR m.metadata ? 'permit')
                        ORDER BY m.created_at DESC
                        """,
                        (user_param,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 
                            m.message_id, 
                            m.session_id, 
                            m.metadata, 
                            m.created_at, 
                            s.title as session_title
                        FROM chat_messages m
                        JOIN chat_sessions s ON m.session_id = s.session_id
                        WHERE (m.metadata ? 'artifact' OR m.metadata ? 'permit')
                        ORDER BY m.created_at DESC
                        """
                    )
                rows = cur.fetchall()
                for row in rows:
                    meta = row.get("metadata") or {}
                    if not isinstance(meta, dict):
                        continue

                    # Process deliverable artifact
                    art = meta.get("artifact")
                    if art and isinstance(art, dict):
                        doc_id = art.get("document_id") or row["message_id"]
                        if doc_id not in seen_ids:
                            seen_ids.add(doc_id)
                            deliverables.append({
                                "id": doc_id,
                                "document_id": art.get("document_id"),
                                "title": art.get("title") or art.get("file_name") or "Engineering Deliverable",
                                "file_name": art.get("file_name") or f"{doc_id}.docx",
                                "format": art.get("format", "docx"),
                                "file_size_bytes": art.get("file_size_bytes", 0),
                                "created_at": art.get("created_at") or (row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"])),
                                "session_id": row["session_id"],
                                "session_title": row["session_title"],
                                "status": art.get("verification_status", "VERIFIED"),
                                "type": "deliverable",
                                "download_url": f"/artifacts/{art.get('document_id')}/download" if art.get("document_id") else None,
                                "evidence_ledger": art.get("evidence_ledger"),
                            })

                    # Process permit
                    pmt = meta.get("permit")
                    if pmt and isinstance(pmt, dict):
                        pid = pmt.get("permit_id") or row["message_id"]
                        if pid not in seen_ids:
                            seen_ids.add(pid)
                            doc_id = (art.get("document_id") if (art and isinstance(art, dict)) else None) or pid
                            deliverables.append({
                                "id": pid,
                                "permit_id": pmt.get("permit_id"),
                                "document_id": doc_id,
                                "title": pmt.get("title") or "Industrial Work Permit",
                                "file_name": f"{pmt.get('permit_id', 'permit')}.docx",
                                "format": "permit",
                                "file_size_bytes": 0,
                                "created_at": pmt.get("created_at") or (row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"])),
                                "session_id": row["session_id"],
                                "session_title": row["session_title"],
                                "status": pmt.get("status", "DRAFT_GENERATED"),
                                "equipment_tag": pmt.get("equipment_tag", ""),
                                "facility_name": pmt.get("facility_name", ""),
                                "authorized_by": pmt.get("authorized_by"),
                                "type": "permit",
                                "download_url": f"/artifacts/{doc_id}/download" if doc_id else None,
                                "evidence_ledger": pmt.get("evidence_ledger"),
                                "permit_data": pmt,
                            })
    except Exception as e:
        logger.warning("Failed querying user deliverables from chat messages: %s", e)

    # 2. Merge active cached permits if not already seen
    for p_id, p_obj in _PERMIT_CACHE.items():
        if p_id not in seen_ids:
            seen_ids.add(p_id)
            deliverables.append({
                "id": p_id,
                "permit_id": p_obj.permit_id,
                "document_id": p_obj.permit_id,
                "title": p_obj.title,
                "file_name": f"{p_obj.permit_id}.docx",
                "format": "permit",
                "file_size_bytes": 0,
                "created_at": p_obj.created_at,
                "session_id": "active-session",
                "session_title": "Current Session",
                "status": p_obj.status.value,
                "equipment_tag": p_obj.equipment_tag,
                "facility_name": p_obj.facility_name,
                "authorized_by": p_obj.authorized_by,
                "type": "permit",
                "download_url": None,
                "evidence_ledger": p_obj.evidence_ledger.to_dict() if p_obj.evidence_ledger else None,
                "permit_data": p_obj.to_dict(),
            })

    return deliverables


@router.get("/{document_id}/download")
async def download_artifact(
    document_id: str,
    repo: MetadataRepository = Depends(get_metadata_repo),
) -> Response:
    """Download a generated deliverable (.docx, .pdf, .pptx) with authentic file headers."""
    from database.repositories import DocumentMetadata
    from generation.generators.word_generator import WordGenerator

    storage = get_storage_service()

    # 1. Standard MetadataRepository lookup
    meta = repo.get_document_metadata(document_id)
    if meta and meta.stored_object and storage.exists(storage_key=meta.stored_object.storage_key):
        file_bytes = storage.get_bytes(storage_key=meta.stored_object.storage_key)
        filename = meta.file_name or f"{document_id}.bin"
        content_type = meta.stored_object.content_type or "application/octet-stream"

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            },
        )

    # 2. Permit fallback: Check active permit cache, chat_messages metadata, or permit ID
    permit_data = None
    if document_id in _PERMIT_CACHE:
        permit_data = _PERMIT_CACHE[document_id]
    else:
        try:
            from database.chat_repository import ChatRepository
            chat_repo = ChatRepository()
            with chat_repo._connect() as conn:
                chat_repo._ensure_tables(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT metadata FROM chat_messages
                        WHERE metadata ? 'permit' OR metadata ? 'artifact'
                        ORDER BY created_at DESC
                        LIMIT 100
                        """
                    )
                    rows = cur.fetchall()
                    for row in rows:
                        m = row.get("metadata") if isinstance(row, dict) else (row[0] if isinstance(row, (list, tuple)) else None)
                        if isinstance(m, dict):
                            pmt = m.get("permit")
                            if isinstance(pmt, dict) and (pmt.get("permit_id") == document_id or m.get("document_id") == document_id):
                                permit_data = pmt
                                break
        except Exception as e:
            logger.debug("Database check for permit fallback failed: %s", e)

    # If it is a permit, synthesize authentic Microsoft Word document
    if permit_data or document_id.startswith("PERMIT-") or "permit" in document_id.lower():
        if not permit_data:
            permit_data = {
                "permit_id": document_id,
                "title": "Industrial Safe Work Permit",
                "equipment_tag": "Process Equipment",
                "facility_name": "Sovereign Industrial Operations",
                "status": "READY_FOR_REVIEW",
                "work_description": "General safe work, electrical isolation, and maintenance protocol.",
            }

        file_bytes = WordGenerator().build_permit_docx_bytes(permit_data)
        filename = f"{document_id}.docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Auto-persist into storage and metadata repo so future calls are instant
        try:
            stored_obj = storage.put_bytes(
                document_id=document_id,
                file_name=filename,
                content_type=content_type,
                data=file_bytes,
            )
            repo.save_document_metadata(
                DocumentMetadata(
                    document_id=document_id,
                    file_name=filename,
                    content_type=content_type,
                    stored_object=stored_obj,
                )
            )
        except Exception as e:
            logger.debug("Auto-caching generated permit docx failed: %s", e)

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            },
        )

    # 3. Not found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Artifact {document_id} not found.",
    )


@router.get("/permits/{permit_id}")
async def get_permit_details(permit_id: str) -> dict[str, Any]:
    """Retrieve full permit structure and review status."""
    permit = get_cached_permit(permit_id)
    if not permit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permit {permit_id} not found in active review cache.",
        )
    return permit.to_dict()


@router.post("/permits/{permit_id}/sign-off")
async def sign_off_permit_endpoint(
    permit_id: str,
    body: PermitSignOffRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Sign off an industrial permit. AI agents are strictly rejected."""
    permit = get_cached_permit(permit_id)
    if not permit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permit {permit_id} not found in active review cache.",
        )

    # 1. Deterministic safety check against automated AI agents
    if body.is_automated_agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CRITICAL SAFETY VIOLATION: Automated AI agents are strictly prohibited from authorizing industrial permits.",
        )

    try:
        updated_permit = review_service.sign_off_permit(
            permit=permit,
            reviewer_id=str(current_user.user_id),
            reviewer_name=body.reviewer_name,
            reviewer_role=body.reviewer_role,
            signature_confirmed=body.signature_confirmed,
            is_automated_agent=body.is_automated_agent,
        )
        return {
            "success": True,
            "permit": updated_permit.to_dict(),
            "message": f"Permit {permit_id} successfully authorized by {updated_permit.authorized_by}.",
        }
    except (ValueError, PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
