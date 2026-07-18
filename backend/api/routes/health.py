"""Health check endpoint for system readiness and diagnostics."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter(prefix="/health", tags=["System"])


class ServiceStatus(BaseModel):
    status: str
    configured: bool
    connected: bool = False
    latency_ms: int = 0


class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, ServiceStatus]


@router.get("", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """System readiness probe.

    Checks connectivity to all configured external services.
    Currently returns dummy values pending DI integration for latency checks.
    """
    # TODO: Connect to app.state DI containers to ping services for real latency.
    return HealthResponse(
        status="ok",
        version="1.0.0",
        services={
            "neo4j": ServiceStatus(status="up", configured=True, connected=True, latency_ms=12),
            "qdrant": ServiceStatus(status="up", configured=True, connected=True, latency_ms=8),
            "postgres": ServiceStatus(status="up", configured=True, connected=True, latency_ms=4),
            "redis": ServiceStatus(status="up", configured=True, connected=True, latency_ms=2),
            "openrouter": ServiceStatus(status="up", configured=True, connected=True, latency_ms=45),
        }
    )
