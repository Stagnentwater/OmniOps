"""Centralized strict environment configuration for API and worker processes."""

from functools import lru_cache
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, AliasChoices
from dotenv import load_dotenv

# Load .env file from project root into os.environ
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class FastAPISettings(BaseSettings):
    """Settings for FastAPI runtime behavior."""
    app_name: str = Field(default="OmniOps API", validation_alias="FASTAPI_APP_NAME")
    host: str = Field(default="0.0.0.0", validation_alias="FASTAPI_HOST")
    port: int = Field(default=8000, validation_alias="FASTAPI_PORT")


class QuerySettings(BaseSettings):
    """Settings for query-time conversational context."""

    conversation_history_limit: int = Field(
        default=10,
        ge=1,
        validation_alias="CONVERSATION_HISTORY_LIMIT",
    )


class RedisSettings(BaseSettings):
    """Settings for Redis queue connectivity."""
    url: str | None = Field(default=None, validation_alias="REDIS_URL")
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
    url: str | None = Field(default=None, validation_alias="DATABASE_URL", description="Full Postgres DSN string")
    host: str = Field(default="postgres", validation_alias="POSTGRES_HOST")
    port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    db: str = Field(default="omniops", validation_alias="POSTGRES_DB")
    user: str = Field(default="omniops", validation_alias="POSTGRES_USER")
    password: str = Field(default="omniops", validation_alias="POSTGRES_PASSWORD")

    @property
    def dsn(self) -> str:
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class Neo4jSettings(BaseSettings):
    """Settings for Neo4j connectivity."""
    uri: str = Field(..., validation_alias="NEO4J_URI")
    user: str = Field(default="neo4j", validation_alias=AliasChoices("NEO4J_USERNAME", "NEO4J_USER"))
    password: str = Field(..., validation_alias="NEO4J_PASSWORD")


class QdrantSettings(BaseSettings):
    """Settings for Qdrant connectivity."""
    url_override: str | None = Field(default=None, validation_alias="QDRANT_URL")
    api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    host: str = Field(default="qdrant", validation_alias="QDRANT_HOST")
    port: int = Field(default=6333, validation_alias="QDRANT_PORT")

    @property
    def url(self) -> str:
        """Build the base URL for Qdrant HTTP API."""
        if self.url_override:
            return self.url_override
        return f"http://{self.host}:{self.port}"


class OpenRouterSettings(BaseSettings):
    """Settings for OpenRouter integration (legacy RAG fallback)."""
    base_url: str = Field(default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL")
    api_key: str = Field(..., validation_alias="OPENROUTER_API_KEY")
    model: str = Field(..., validation_alias="OPENROUTER_MODEL")


class AgentSettings(BaseSettings):
    """Settings for the agentic orchestration loop."""
    max_iterations: int = Field(default=8, ge=1, le=20, validation_alias="AGENT_MAX_ITERATIONS")
    timeout_seconds: float = Field(default=120.0, ge=10.0, validation_alias="AGENT_TIMEOUT_SECONDS")
    enabled: bool = Field(default=True, validation_alias="AGENT_ENABLED")


class StorageSettings(BaseSettings):
    """Settings for storage backend selection."""
    backend: str = Field(default="local", validation_alias="STORAGE_BACKEND")
    local_root: str = Field(default="/data/storage", validation_alias="STORAGE_LOCAL_ROOT")


class EmbeddingSettings(BaseSettings):
    """Settings for embedding model selection."""
    model_config = SettingsConfigDict(protected_namespaces=())
    model_name: str = Field(default="BAAI/bge-m3", validation_alias="EMBEDDING_MODEL_NAME")


class VisionSettings(BaseSettings):
    """Settings for the image ingestion vision pipeline."""
    model_config = SettingsConfigDict(protected_namespaces=())
    model_name: str = Field(default="gemma3:4b", validation_alias="VISION_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    max_image_size_mb: int = Field(default=20, validation_alias="VISION_MAX_IMAGE_SIZE_MB")
    max_resolution: int = Field(default=2048, validation_alias="VISION_MAX_RESOLUTION")
    max_concurrent_jobs: int = Field(default=1, validation_alias="VISION_MAX_CONCURRENT_JOBS")
    max_batch_size: int = Field(default=10, validation_alias="VISION_MAX_BATCH_SIZE")
    context_window: int = Field(default=4096, validation_alias="VISION_CONTEXT_WINDOW")


class ModelRegistry(BaseSettings):
    """Centralized model name configuration for multi-model routing."""
    model_config = SettingsConfigDict(protected_namespaces=())
    reasoning_model: str = Field(default="llama3.2", validation_alias="REASONING_MODEL")
    vision_model: str = Field(default="gemma3:4b", validation_alias="VISION_MODEL")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", validation_alias="EMBEDDING_MODEL_NAME")
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")


class AuthSettings(BaseSettings):
    """Settings for authentication and token validation."""
    secret_key: str = Field(
        default="vigilops-secret-key-change-in-production-32bytes-min",
        validation_alias="AUTH_SECRET_KEY",
    )
    algorithm: str = Field(default="HS256", validation_alias="AUTH_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=1440,
        validation_alias="AUTH_ACCESS_TOKEN_EXPIRE_MINUTES",
    )


class Settings(BaseSettings):
    """Root settings object used by API and worker."""
    
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=(".env", "../.env"), extra="ignore")

    fastapi: FastAPISettings = Field(default_factory=FastAPISettings)
    query: QuerySettings = Field(default_factory=QuerySettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)  # Required
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)           # Required
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)        # Required
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings) # Required
    storage: StorageSettings = Field(default_factory=StorageSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    models: ModelRegistry = Field(default_factory=ModelRegistry)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load, validate, and cache settings from process environment. Fails fast if required variables are missing."""
    return Settings()

