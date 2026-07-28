"""Health check endpoint for system readiness and diagnostics."""

import time
import logging
from typing import Dict, Any, List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

import psycopg
import neo4j
import redis
# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
from rq import Worker as RQWorker

from config.settings import get_settings

router = APIRouter(prefix="/health", tags=["System"])
logger = logging.getLogger(__name__)


class ServiceStatus(BaseModel):
    status: str
    configured: bool
    connected: bool = False
    latency_ms: int = 0
    error: str | None = None


class WorkerStatus(BaseModel):
    enabled: bool
    thread_alive: bool = False
    thread_name: str | None = None
    daemon: bool | None = None
    queue: str
    registered_in_redis: bool = False
    registered_workers: int = 0
    worker_ids: List[str] = []
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, ServiceStatus]
    worker: WorkerStatus


@router.get("", response_model=HealthResponse)
async def get_health(request: Request) -> HealthResponse:
    """System readiness probe.

    Checks connectivity to all configured external services with bounded timeouts
    and inspects the status of the embedded RQ worker.
    """
    settings = get_settings()
    services = {}
    
    # 1. Postgres
    try:
        start = time.perf_counter()
        with psycopg.connect(settings.postgres.dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        latency = int((time.perf_counter() - start) * 1000)
        services["postgres"] = ServiceStatus(status="up", configured=True, connected=True, latency_ms=latency)
    except Exception as e:
        logger.error(f"Postgres connection failed: {e}")
        services["postgres"] = ServiceStatus(status="down", configured=True, connected=False, error=str(e))
        
    # 2. Neo4j
    try:
        start = time.perf_counter()
        with neo4j.GraphDatabase.driver(settings.neo4j.uri, auth=(settings.neo4j.user, settings.neo4j.password)) as driver:
            driver.verify_connectivity()
        latency = int((time.perf_counter() - start) * 1000)
        services["neo4j"] = ServiceStatus(status="up", configured=True, connected=True, latency_ms=latency)
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        services["neo4j"] = ServiceStatus(status="down", configured=True, connected=False, error=str(e))
        
    # 3. Redis
    redis_client = None
    try:
        start = time.perf_counter()
        if settings.redis.url:
            r = redis.Redis.from_url(settings.redis.url, socket_connect_timeout=3)
        else:
            r = redis.Redis(host=settings.redis.host, port=settings.redis.port, db=settings.redis.db, socket_connect_timeout=3)
        r.ping()
        redis_client = r
        latency = int((time.perf_counter() - start) * 1000)
        services["redis"] = ServiceStatus(status="up", configured=True, connected=True, latency_ms=latency)
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        services["redis"] = ServiceStatus(status="down", configured=True, connected=False, error=str(e))
        
    # 4. Qdrant
    try:
        start = time.perf_counter()
        client = QdrantClient(url=settings.qdrant.url, api_key=settings.qdrant.api_key, timeout=3)
        client.get_collections()
        latency = int((time.perf_counter() - start) * 1000)
        services["qdrant"] = ServiceStatus(status="up", configured=True, connected=True, latency_ms=latency)
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        services["qdrant"] = ServiceStatus(status="down", configured=True, connected=False, error=str(e))
        
    # Overall status
    overall_status = "ok" if all(s.connected for s in services.values()) else "degraded"
    
    # 5. Worker Status
    worker_thread = getattr(request.app.state, "worker_thread", None)
    thread_alive = worker_thread.is_alive() if worker_thread else False
    thread_name = worker_thread.name if worker_thread else None
    daemon = worker_thread.daemon if worker_thread else None

    registered_in_redis = False
    registered_workers = 0
    worker_ids: List[str] = []
    worker_error = None

    if redis_client:
        try:
            rq_workers = RQWorker.all(connection=redis_client)
            registered_workers = len(rq_workers)
            worker_ids = [w.name for w in rq_workers]
            registered_in_redis = registered_workers > 0
        except Exception as e:
            logger.warning(f"Failed to query RQ workers from Redis: {e}")
            worker_error = str(e)
    else:
        worker_error = "Redis connection unavailable"

    worker_status = WorkerStatus(
        enabled=settings.fastapi.embed_worker,
        thread_alive=thread_alive,
        thread_name=thread_name,
        daemon=daemon,
        queue=settings.queue.name,
        registered_in_redis=registered_in_redis,
        registered_workers=registered_workers,
        worker_ids=worker_ids,
        error=worker_error,
    )

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        services=services,
        worker=worker_status
    )

