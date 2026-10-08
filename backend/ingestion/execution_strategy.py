"""Ingestion job execution strategies.

Provides two execution paths for ingestion jobs:
1. RQExecutionStrategy — Uses Redis/RQ for production deployments (Linux).
   Jobs are idempotent and retryable with configurable retry policy.
2. BackgroundTaskStrategy — Uses FastAPI BackgroundTasks for local
   development on Windows where RQ/fork() is not available.

The active strategy is selected automatically based on platform
and Redis availability. Users never configure this manually.

Windows compatibility note:
    RQ relies on os.fork() which is not available on Windows.
    The BackgroundTaskStrategy provides identical behavior using
    FastAPI's built-in BackgroundTasks (asyncio-based, in-process).
    This is documented and tested as the official Windows dev path.
"""

from __future__ import annotations

import logging
import platform
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionStrategy(ABC):
    """Abstract base for ingestion job execution."""

    @abstractmethod
    def enqueue(
        self,
        *,
        job_id: str,
        document_id: str,
        file_name: str,
        background_tasks: Any = None,
    ) -> str:
        """Enqueue an ingestion job for execution.

        Args:
            job_id: The lifecycle job ID from the metadata repository.
            document_id: The document's content-addressed ID.
            file_name: Original filename.
            background_tasks: FastAPI BackgroundTasks (only for BackgroundTaskStrategy).

        Returns:
            The execution job ID (RQ job ID or lifecycle job ID).
        """

    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the strategy."""


class BackgroundTaskStrategy(ExecutionStrategy):
    """Execute ingestion via FastAPI BackgroundTasks (Windows-compatible).

    This is the default strategy for local Windows development.
    Jobs run in-process on the event loop thread pool.

    Note: This does NOT provide retry or persistence across restarts.
    For production deployments, use RQExecutionStrategy.
    """

    def enqueue(
        self,
        *,
        job_id: str,
        document_id: str,
        file_name: str,
        background_tasks: Any = None,
    ) -> str:
        if background_tasks is None:
            raise ValueError(
                "BackgroundTaskStrategy requires a FastAPI BackgroundTasks instance."
            )

        from ingestion.orchestrator import process_ingestion_job

        background_tasks.add_task(
            process_ingestion_job,
            lifecycle_job_id=job_id,
            document_id=document_id,
            file_name=file_name,
        )
        logger.info(
            "Job %s enqueued via BackgroundTasks (document=%s)",
            job_id,
            document_id,
        )
        return job_id

    def name(self) -> str:
        return "BackgroundTasks (Windows-compatible)"


class RQExecutionStrategy(ExecutionStrategy):
    """Execute ingestion via Redis/RQ (Linux deployment).

    Jobs are:
    - Idempotent: The same document_id produces the same result regardless
      of how many times the job runs (content-addressed storage + upserts).
    - Retryable: Failed jobs are automatically retried per the configured
      retry policy (max retries, backoff intervals).
    - Persistent: Job state survives process restarts via Redis.
    """

    def __init__(
        self,
        redis_url: str,
        queue_name: str = "default",
        job_timeout: int = 900,
        retry_max: int = 3,
        retry_intervals: list[int] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._job_timeout = job_timeout
        self._retry_max = retry_max
        self._retry_intervals = retry_intervals or [10, 30, 60]

    def enqueue(
        self,
        *,
        job_id: str,
        document_id: str,
        file_name: str,
        background_tasks: Any = None,
    ) -> str:
        try:
            from redis import Redis
            from rq import Queue, Retry
        except ImportError:
            logger.warning(
                "redis/rq not installed. Falling back to BackgroundTaskStrategy."
            )
            fallback = BackgroundTaskStrategy()
            return fallback.enqueue(
                job_id=job_id,
                document_id=document_id,
                file_name=file_name,
                background_tasks=background_tasks,
            )

        redis_conn = Redis.from_url(self._redis_url)
        queue = Queue(self._queue_name, connection=redis_conn)

        retry = Retry(
            max=self._retry_max,
            interval=self._retry_intervals,
        )

        rq_job = queue.enqueue(
            "ingestion.orchestrator.process_ingestion_job",
            kwargs={
                "lifecycle_job_id": job_id,
                "document_id": document_id,
                "file_name": file_name,
            },
            job_id=job_id,  # Use lifecycle ID for idempotency
            job_timeout=self._job_timeout,
            retry=retry,
        )

        logger.info(
            "Job %s enqueued via RQ (document=%s, queue=%s, retry_max=%d)",
            rq_job.id,
            document_id,
            self._queue_name,
            self._retry_max,
        )
        return rq_job.id

    def name(self) -> str:
        return "RQ (Redis-backed, retryable)"


def get_execution_strategy() -> ExecutionStrategy:
    """Auto-select the best execution strategy for the current environment.

    Selection logic:
    1. Windows → always BackgroundTaskStrategy (RQ uses fork()).
    2. Linux + REDIS_URL set → RQExecutionStrategy.
    3. Linux + no REDIS_URL → BackgroundTaskStrategy.

    Returns:
        The appropriate ExecutionStrategy instance.
    """
    is_windows = platform.system() == "Windows"

    if is_windows:
        logger.info("Windows detected. Using BackgroundTaskStrategy.")
        return BackgroundTaskStrategy()

    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        from config.settings import get_settings
        settings = get_settings()
        strategy = RQExecutionStrategy(
            redis_url=redis_url,
            queue_name=settings.queue.name,
            job_timeout=settings.queue.job_timeout_seconds,
            retry_max=settings.queue.retry_max,
            retry_intervals=settings.queue.retry_intervals_seconds,
        )
        logger.info("Redis available. Using RQExecutionStrategy.")
        return strategy

    logger.info("No Redis URL configured. Using BackgroundTaskStrategy.")
    return BackgroundTaskStrategy()
