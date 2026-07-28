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


class EmbeddedWorker(SimpleWorker):
    """RQ worker subclass safe to run in a non-main thread.

    ``Worker.work()`` calls ``_install_signal_handlers()`` which uses
    ``signal.signal()`` — only allowed in Python's main thread. This
    subclass overrides that method with a no-op so the worker can run
    inside a daemon thread (e.g., within the FastAPI process).

    Inherits from ``SimpleWorker`` (no fork) so it works on all
    platforms including Windows.
    """

    def _install_signal_handlers(self) -> None:  # noqa: D102
        """No-op: signal handlers cannot be installed outside the main thread."""
        pass


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


def start_worker(*, embedded: bool = False) -> None:
    """Start the RQ worker. This is a **blocking** call.

    Creates a Redis connection, selects the appropriate worker class
    for the current platform/mode, and begins polling the configured queue.

    Args:
        embedded: When True, uses ``EmbeddedWorker`` (no signal handlers,
                  no scheduler) so it can safely run in a daemon thread.
                  When False (default), uses the standard platform worker
                  (``Worker`` on Linux, ``SimpleWorker`` on Windows).

    This function never returns under normal operation.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")

    settings = get_settings()
    redis_connection = _create_redis_connection()

    if embedded:
        worker_class = EmbeddedWorker
        # Scheduler spawns a separate process and also requires signal handling;
        # OmniOps does not use scheduled/delayed jobs, so disable it.
        with_scheduler = False
    else:
        worker_class = SimpleWorker if sys.platform == "win32" else Worker
        with_scheduler = True

    logger.info(
        f"Starting RQ worker on queue: '{settings.queue.name}' "
        f"(class={worker_class.__name__}, embedded={embedded})"
    )
    worker = worker_class([settings.queue.name], connection=redis_connection)
    worker.work(with_scheduler=with_scheduler)


if __name__ == "__main__":
    start_worker()
