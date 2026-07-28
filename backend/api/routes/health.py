"""Health check endpoint for system readiness and diagnostics."""

import time
import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Dict, Any

import psycopg
import neo4j
import redis
# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient

from config.settings import get_settings

router = APIRouter(prefix="/health", tags=["System"])
logger = logging.getLogger(__name__)


class ServiceStatus(BaseModel):
    status: str
    configured: bool
    connected: bool = False
    latency_ms: int = 0
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, ServiceStatus]


@router.get("", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """System readiness probe.

    Checks connectivity to all configured external services with bounded timeouts.
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
    try:
        start = time.perf_counter()
        if settings.redis.url:
            r = redis.Redis.from_url(settings.redis.url, socket_connect_timeout=3)
        else:
            r = redis.Redis(host=settings.redis.host, port=settings.redis.port, db=settings.redis.db, socket_connect_timeout=3)
        r.ping()
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
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        services=services
    )
