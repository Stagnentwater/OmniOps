"""RQ worker entrypoint for OmniOps ingestion jobs."""

import logging

from redis import Redis
from rq import Worker

from config.settings import get_settings


def main() -> None:
    """Start the default RQ worker using Redis from environment settings."""
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    redis_connection = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.db,
    )
    import sys
    from rq.worker import SimpleWorker
    
    worker_class = SimpleWorker if sys.platform == "win32" else Worker
    worker = worker_class([settings.queue.name], connection=redis_connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
