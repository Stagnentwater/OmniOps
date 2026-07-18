"""Upload orchestration service integrating storage, metadata, and queueing."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import logging

from database.repositories import DocumentMetadata, MetadataRepository
from ingestion.orchestrator import process_ingestion_job
from storage.factory import get_storage_service


logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv"}


class UploadServiceError(Exception):
    """Structured upload orchestration error."""

    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class UploadResult:
    """Result returned after successful upload enqueue flow."""

    document_id: str
    job_id: str
    status: str


def _emit_upload_log(
    *,
    document_id: str,
    stage: str,
    status: str,
    error: str | None = None,
) -> None:
    payload = {
        "document_id": document_id,
        "stage": stage,
        "status": status,
        "error": error,
    }
    logger.info("%s", json.dumps(payload))


def _validate_upload(*, file_name: str, data: bytes) -> None:
    if not file_name.strip():
        raise UploadServiceError(
            code="invalid_file_name",
            message="File name is required.",
            status_code=400,
        )
    extension = ""
    if "." in file_name:
        extension = "." + file_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadServiceError(
            code="unsupported_file_type",
            message="Only PDF, DOCX, and CSV are supported in MVP.",
            status_code=400,
        )
    if not data:
        raise UploadServiceError(
            code="empty_file",
            message="Uploaded file is empty.",
            status_code=400,
        )


def handle_upload(
    *,
    file_name: str,
    content_type: str,
    data: bytes,
    background_tasks,
) -> UploadResult:
    """Execute upload flow: validate, store, persist metadata, create job, enqueue."""
    _validate_upload(file_name=file_name, data=data)
    document_id = sha256(data).hexdigest()
    storage_service = get_storage_service()
    repository = MetadataRepository()

    try:
        stored_object = storage_service.put_bytes(
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
            data=data,
        )
    except Exception as exc:
        _emit_upload_log(
            document_id=document_id,
            stage="STORE_FILE",
            status="FAILED",
            error=str(exc),
        )
        raise UploadServiceError(
            code="storage_write_failed",
            message="Failed to store uploaded file.",
            status_code=500,
        ) from exc

    try:
        repository.save_document_metadata(
            DocumentMetadata(
                document_id=document_id,
                file_name=file_name,
                content_type=content_type,
                stored_object=stored_object,
            )
        )
    except Exception as exc:
        _emit_upload_log(
            document_id=document_id,
            stage="PERSIST_METADATA",
            status="FAILED",
            error=str(exc),
        )
        try:
            storage_service.delete(storage_key=stored_object.storage_key)
        except Exception as delete_error:
            _emit_upload_log(
                document_id=document_id,
                stage="COMPENSATING_DELETE",
                status="FAILED",
                error=str(delete_error),
            )
        raise UploadServiceError(
            code="metadata_persist_failed",
            message="Failed to persist document metadata.",
            status_code=500,
        ) from exc

    job_id = repository.create_ingestion_job(document_id=document_id)
    try:
        # Bypass RQ on Windows and use FastAPI BackgroundTasks directly
        background_tasks.add_task(
            process_ingestion_job,
            lifecycle_job_id=job_id,
            document_id=document_id,
            file_name=file_name,
        )
        repository.mark_job_enqueued(job_id=job_id, rq_job_id=job_id)
    except Exception as exc:
        repository.mark_job_queue_failed(job_id=job_id, error=str(exc))
        _emit_upload_log(
            document_id=document_id,
            stage="ENQUEUE_JOB",
            status="FAILED",
            error=str(exc),
        )
        raise UploadServiceError(
            code="enqueue_failed",
            message="Failed to enqueue ingestion job. Document was stored for future re-enqueue.",
            status_code=503,
        ) from exc

    _emit_upload_log(
        document_id=document_id,
        stage="UPLOAD_FLOW",
        status="COMPLETED",
    )
    return UploadResult(document_id=document_id, job_id=job_id, status="PENDING")
