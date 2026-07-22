"""OmniOps backend FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

from config.settings import get_settings
from api.routes.health import router as health_router
from api.routes.documents import router as documents_router
from api.routes.uploads import router as uploads_router
from api.routes.query import router as query_router
from api.routes.knowledge import router as knowledge_router
from api.routes.chat import router as chat_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
logger = logging.getLogger(__name__)

# Load settings immediately. This will fail fast if required env vars are missing.
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    logger.info("Initializing OmniOps backend...")
    
    # Check OpenRouter Configuration
    if not settings.openrouter.api_key:
        logger.error("OPENROUTER_API_KEY is missing. Failsafe activated.")
        raise RuntimeError("OPENROUTER_API_KEY is required for startup.")
        
    # TODO: Instantiate Neo4j, Qdrant, Postgres Connection Managers here
    # app.state.neo4j = Neo4jConnectionManager(settings.neo4j)
    # app.state.qdrant = QdrantConnectionManager(settings.qdrant)
    # app.state.postgres = PostgresConnectionManager(settings.postgres)
    
    logger.info("OmniOps backend successfully initialized.")
    yield
    
    logger.info("Shutting down OmniOps backend...")
    # TODO: Close connection pools


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.fastapi.app_name,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(uploads_router)
app.include_router(query_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
