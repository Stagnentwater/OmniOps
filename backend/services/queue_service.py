"""Queue service for ingestion background jobs."""

from redis import Redis
from rq import Queue, Retry

from config.settings import get_settings
from ingestion.orchestrator import process_ingestion_job


def enqueue_ingestion_job(
    *,
    lifecycle_job_id: str,
    document_id: str,
    file_name: str,
) -> str:
    """Enqueue the ingestion orchestrator job and return RQ job ID."""
    settings = get_settings()
    redis_connection = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.db,
    )
    queue = Queue(name=settings.queue.name, connection=redis_connection)
    retry_policy = Retry(
        max=settings.queue.retry_max,
        interval=settings.queue.retry_intervals_seconds,
    )
    job = queue.enqueue(
        process_ingestion_job,
        kwargs={
            "lifecycle_job_id": lifecycle_job_id,
            "document_id": document_id,
            "file_name": file_name,
        },
        job_id=lifecycle_job_id,
        retry=retry_policy,
        job_timeout=settings.queue.job_timeout_seconds,
    )
    return job.id
