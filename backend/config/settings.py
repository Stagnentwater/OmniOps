"""Centralized strict environment configuration for API and worker processes."""

from functools import lru_cache
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from dotenv import load_dotenv

# Load .env file from project root into os.environ
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class FastAPISettings(BaseSettings):
    """Settings for FastAPI runtime behavior."""
    app_name: str = Field(default="OmniOps API", validation_alias="FASTAPI_APP_NAME")
    host: str = Field(default="0.0.0.0", validation_alias="FASTAPI_HOST")
    port: int = Field(default=8000, validation_alias="FASTAPI_PORT")


class RedisSettings(BaseSettings):
    """Settings for Redis queue connectivity."""
    host: str = Field(default="redis", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    db: int = Field(default=0, validation_alias="REDIS_DB")


class QueueSettings(BaseSettings):
    """Settings for RQ queue behavior and retry policy."""
    name: str = Field(default="default", validation_alias="RQ_QUEUE_NAME")
    job_timeout_seconds: int = Field(default=900, validation_alias="RQ_JOB_TIMEOUT_SECONDS")
    retry_max: int = Field(default=3, validation_alias="RQ_RETRY_MAX")
    retry_intervals_seconds: list[int] = Field(default=[10, 30, 60], validation_alias="RQ_RETRY_INTERVALS_SECONDS")

    @field_validator("retry_intervals_seconds", mode="before")
    @classmethod
    def parse_intervals(cls, v: str | list[int]) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v


class PostgresSettings(BaseSettings):
    """Settings for PostgreSQL connectivity."""
    dsn: str = Field(..., validation_alias="POSTGRES_URL", description="Full Postgres DSN string")


class Neo4jSettings(BaseSettings):
    """Settings for Neo4j connectivity."""
    uri: str = Field(..., validation_alias="NEO4J_URI")
    user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    password: str = Field(..., validation_alias="NEO4J_PASSWORD")


class QdrantSettings(BaseSettings):
    """Settings for Qdrant connectivity."""
    host: str = Field(..., validation_alias="QDRANT_HOST")
    port: int = Field(default=6333, validation_alias="QDRANT_PORT")

    @property
    def url(self) -> str:
        """Build the base URL for Qdrant HTTP API."""
        return f"http://{self.host}:{self.port}"


class OpenRouterSettings(BaseSettings):
    """Settings for OpenRouter integration."""
    base_url: str = Field(default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL")
    api_key: str = Field(..., validation_alias="OPENROUTER_API_KEY")
    model: str = Field(..., validation_alias="OPENROUTER_MODEL")


class StorageSettings(BaseSettings):
    """Settings for storage backend selection."""
    backend: str = Field(default="local", validation_alias="STORAGE_BACKEND")
    local_root: str = Field(default="/data/storage", validation_alias="STORAGE_LOCAL_ROOT")


class EmbeddingSettings(BaseSettings):
    """Settings for embedding model selection."""
    model_config = SettingsConfigDict(protected_namespaces=())
    model_name: str = Field(default="BAAI/bge-m3", validation_alias="EMBEDDING_MODEL_NAME")


class Settings(BaseSettings):
    """Root settings object used by API and worker."""
    
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=(".env", "../.env"), extra="ignore")

    fastapi: FastAPISettings = Field(default_factory=FastAPISettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)  # Required
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)           # Required
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)        # Required
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings) # Required
    storage: StorageSettings = Field(default_factory=StorageSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load, validate, and cache settings from process environment. Fails fast if required variables are missing."""
    return Settings()
