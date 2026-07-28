"""RQ worker entrypoint for OmniOps ingestion jobs.

Provides a reusable ``start_worker()`` function that can be called:
  - Directly via ``python worker.py`` (standalone mode).
  - From within the FastAPI lifespan (embedded mode, see main.py).

The worker polls Redis and executes queued ingestion jobs.
This module does NOT modify queue logic, Redis usage, or job execution.
"""

import logging
import sys

from redis import Redis
from rq import Worker
from rq.worker import SimpleWorker

from config.settings import get_settings


logger = logging.getLogger(__name__)


def _create_redis_connection() -> Redis:
    """Create and verify a Redis connection using application settings.

    Returns:
        A connected Redis client instance.

    Raises:
        Exception: If Redis is unreachable (logged but re-raised).
    """
    settings = get_settings()

    if settings.redis.url:
        logger.info("Connecting to Redis via REDIS_URL...")
        redis_connection = Redis.from_url(settings.redis.url)
    else:
        logger.info(f"Connecting to Redis via REDIS_HOST ({settings.redis.host})...")
        redis_connection = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
        )

    try:
        redis_connection.ping()
        logger.info("Successfully connected to Redis!")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    return redis_connection


def start_worker() -> None:
    """Start the RQ worker. This is a **blocking** call.

    Creates a Redis connection, selects the appropriate worker class
    for the current platform, and begins polling the configured queue.

    On Linux, ``Worker`` (fork-based) is used.
    On Windows, ``SimpleWorker`` (in-process) is used.

    This function never returns under normal operation.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")

    settings = get_settings()
    redis_connection = _create_redis_connection()

    worker_class = SimpleWorker if sys.platform == "win32" else Worker

    logger.info(
        f"Starting RQ worker on queue: '{settings.queue.name}' "
        f"(class={worker_class.__name__})"
    )
    worker = worker_class([settings.queue.name], connection=redis_connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    start_worker()
