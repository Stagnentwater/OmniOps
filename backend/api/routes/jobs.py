"""Ingestion job query endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.repositories import MetadataRepository


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobEventResponse(BaseModel):
    """Serialized ingestion job event entry."""

    status: str
    error: str | None
    created_at: str


class JobStatusResponse(BaseModel):
    """Serialized ingestion job lifecycle response."""

    job_id: str
    document_id: str
    status: str
    rq_job_id: str | None
    error: str | None
    created_at: str
    updated_at: str
    events: list[JobEventResponse]


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    """Return persisted ingestion lifecycle status and transition history."""
    repository = MetadataRepository()
    job = repository.get_ingestion_job(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    events = repository.list_job_events(job_id=job_id)
    return JobStatusResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        status=job.status,
        rq_job_id=job.rq_job_id,
        error=job.error,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        events=[JobEventResponse(**item) for item in events],
    )
