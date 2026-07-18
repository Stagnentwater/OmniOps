"""Upload endpoints for ingestion upload flow."""

from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks
from pydantic import BaseModel

from services.upload_service import UploadServiceError, handle_upload


router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadResponse(BaseModel):
    """Response payload with enqueued job reference."""

    document_id: str
    job_id: str
    status: str


@router.post("", response_model=UploadResponse)
async def enqueue_upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> UploadResponse:
    """Handle document upload and enqueue ingestion processing."""
    content = await file.read()
    try:
        result = handle_upload(
            file_name=file.filename or "",
            content_type=file.content_type or "application/octet-stream",
            data=content,
            background_tasks=background_tasks,
        )
    except UploadServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return UploadResponse(
        document_id=result.document_id,
        job_id=result.job_id,
        status=result.status,
    )
