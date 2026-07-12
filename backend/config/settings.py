"""Centralized environment configuration for API and worker processes."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class FastAPISettings:
    """Settings for FastAPI runtime behavior."""

    app_name: str
    host: str
    port: int


@dataclass(frozen=True)
class RedisSettings:
    """Settings for Redis queue connectivity."""

    host: str
    port: int
    db: int


@dataclass(frozen=True)
class QueueSettings:
    """Settings for RQ queue behavior and retry policy."""

    name: str
    job_timeout_seconds: int
    retry_max: int
    retry_intervals_seconds: list[int]


@dataclass(frozen=True)
class PostgresSettings:
    """Settings for PostgreSQL connectivity."""

    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def dsn(self) -> str:
        """Build a PostgreSQL DSN for future database clients."""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class Neo4jSettings:
    """Settings for Neo4j connectivity."""

    uri: str
    user: str
    password: str


@dataclass(frozen=True)
class QdrantSettings:
    """Settings for Qdrant connectivity."""

    host: str
    port: int

    @property
    def url(self) -> str:
        """Build the base URL for Qdrant HTTP API."""
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True)
class OpenRouterSettings:
    """Settings for OpenRouter integration."""

    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class StorageSettings:
    """Settings for storage backend selection."""

    backend: str
    local_root: str


@dataclass(frozen=True)
class EmbeddingSettings:
    """Settings for embedding model selection."""

    model_name: str


@dataclass(frozen=True)
class Settings:
    """Root settings object used by API and worker."""

    fastapi: FastAPISettings
    redis: RedisSettings
    queue: QueueSettings
    postgres: PostgresSettings
    neo4j: Neo4jSettings
    qdrant: QdrantSettings
    openrouter: OpenRouterSettings
    storage: StorageSettings
    embedding: EmbeddingSettings


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_int_list(name: str, default: list[int]) -> list[int]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return [int(item.strip()) for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from process environment."""
    return Settings(
        fastapi=FastAPISettings(
            app_name=_env("FASTAPI_APP_NAME", "OmniOps API"),
            host=_env("FASTAPI_HOST", "0.0.0.0"),
            port=_env_int("FASTAPI_PORT", 8000),
        ),
        redis=RedisSettings(
            host=_env("REDIS_HOST", "redis"),
            port=_env_int("REDIS_PORT", 6379),
            db=_env_int("REDIS_DB", 0),
        ),
        queue=QueueSettings(
            name=_env("RQ_QUEUE_NAME", "default"),
            job_timeout_seconds=_env_int("RQ_JOB_TIMEOUT_SECONDS", 900),
            retry_max=_env_int("RQ_RETRY_MAX", 3),
            retry_intervals_seconds=_env_int_list("RQ_RETRY_INTERVALS_SECONDS", [10, 30, 60]),
        ),
        postgres=PostgresSettings(
            host=_env("POSTGRES_HOST", "postgres"),
            port=_env_int("POSTGRES_PORT", 5432),
            database=_env("POSTGRES_DB", "omniops"),
            user=_env("POSTGRES_USER", "omniops"),
            password=_env("POSTGRES_PASSWORD", "omniops"),
        ),
        neo4j=Neo4jSettings(
            uri=_env("NEO4J_URI", "bolt://neo4j:7687"),
            user=_env("NEO4J_USER", "neo4j"),
            password=_env("NEO4J_PASSWORD", "password"),
        ),
        qdrant=QdrantSettings(
            host=_env("QDRANT_HOST", "qdrant"),
            port=_env_int("QDRANT_PORT", 6333),
        ),
        openrouter=OpenRouterSettings(
            base_url=_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=_env("OPENROUTER_API_KEY", ""),
            model=_env("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        ),
        storage=StorageSettings(
            backend=_env("STORAGE_BACKEND", "local"),
            local_root=_env("STORAGE_LOCAL_ROOT", "/data/storage"),
        ),
        embedding=EmbeddingSettings(
            model_name=_env("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
        ),
    )
