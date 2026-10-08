"""Dependency Injection configuration for FastAPI."""

from fastapi import Request

from config.settings import get_settings
from database.repositories import MetadataRepository
from database.chat_repository import ChatRepository
from graph.neo4j_repository import Neo4jGraphRepository
from graph.neo4j_connection import Neo4jConnectionManager
from graph.query_service import GraphQueryService
from vector.qdrant_repository import QdrantVectorRepository
from vector.qdrant_connection import QdrantConnectionManager
from vector.embedding_provider import SentenceTransformerEmbeddingProvider
from generation.openrouter_provider import OpenRouterLLMProvider
from retrieval.service import RetrievalService
from generation.service import GenerationService
from generation.prompt_builder import PromptBuilder
from generation.validator import AnswerValidator

from ingestion.orchestrator import IngestionOrchestrator
from ingestion.metadata import extract_metadata
from ingestion.normalizer import clean_whitespace, normalize_encoding, segment_pages, extract_tables, extract_images
from ingestion.chunker import chunk_document
from ingestion.extractor import extract_entities
from ingestion.relationship_extractor import extract_relationships
from ingestion.resolver import resolve_knowledge
from ingestion.models import DocumentContent
import os
from typing import Callable

def get_metadata_repo() -> MetadataRepository:
    return MetadataRepository()

def _get_connections() -> tuple:
    """Get Neo4j and Qdrant connection managers, preferring pooled connections.

    During a FastAPI request, reuses the long-lived connections from
    the application-level ConnectionPool (created at startup).
    For background workers or tests, falls back to creating new connections.

    Returns:
        A tuple of (neo4j_conn, qdrant_conn).
    """
    settings = get_settings()

    # Try to use the app-level connection pool (set in main.py lifespan)
    try:
        from starlette.concurrency import run_in_threadpool  # noqa: F401
        # This import is just a probe to check if we're in a web context.
        # The actual pool comes from a module-level variable.
    except ImportError:
        pass

    # Try the module-level pool reference first
    pool = _app_connection_pool
    if pool is not None and pool.is_initialized:
        neo4j_conn = pool.neo4j
        qdrant_conn = pool.qdrant
        if neo4j_conn is not None and qdrant_conn is not None:
            return neo4j_conn, qdrant_conn

    # Fallback: create new connections (background workers, tests, first startup)
    neo4j_conn = Neo4jConnectionManager(
        settings.neo4j.uri, settings.neo4j.user, settings.neo4j.password,
    )
    qdrant_conn = QdrantConnectionManager(
        url=settings.qdrant.url, api_key=settings.qdrant.api_key,
    )
    return neo4j_conn, qdrant_conn


# Module-level pool reference, set by register_connection_pool()
_app_connection_pool = None


def register_connection_pool(pool) -> None:
    """Register the application-level ConnectionPool for dependency reuse.

    Called by the FastAPI lifespan handler after pool initialization.
    """
    global _app_connection_pool
    _app_connection_pool = pool


def get_query_orchestrator() -> "QueryOrchestrator":
    from query.orchestrator import QueryOrchestrator
    
    settings = get_settings()
    
    # 1. Reuse pooled connections
    neo4j_conn, qdrant_conn = _get_connections()
    graph_repo = Neo4jGraphRepository(neo4j_conn)
    vector_repo = QdrantVectorRepository(qdrant_conn)
    
    # 2. Instantiate Providers
    embedding_provider = SentenceTransformerEmbeddingProvider(settings.embedding.model_name)
    llm_provider = OpenRouterLLMProvider(settings.openrouter)
    
    # 3. Instantiate Services
    graph_query = GraphQueryService(graph_repo)
    retrieval_service = RetrievalService(vector_repo, graph_query, embedding_provider)
    
    generation_service = GenerationService(
        llm_provider=llm_provider,
        prompt_builder=PromptBuilder(),
        validator=AnswerValidator()
    )
    
    return QueryOrchestrator(
        retrieval_service=retrieval_service,
        generation_service=generation_service,
        chat_repository=ChatRepository(),
        conversation_history_limit=settings.query.conversation_history_limit,
    )

def get_ingestion_orchestrator(job_id: str) -> IngestionOrchestrator:
    settings = get_settings()
    
    # Reuse pooled connections
    neo4j_conn, qdrant_conn = _get_connections()
    graph_repo = Neo4jGraphRepository(neo4j_conn)
    vector_repo = QdrantVectorRepository(qdrant_conn)
    embedding_provider = SentenceTransformerEmbeddingProvider(settings.embedding.model_name)
    metadata_repo = MetadataRepository()

    def update_status(state: str):
        metadata_repo.update_job_status(job_id=job_id, status=state)

    def real_parse(file_path: str, doc_id: str) -> DocumentContent:
        """Route to the correct parser based on file extension."""
        import os
        ext = os.path.splitext(file_path)[1].lower()

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        basename = os.path.basename(file_path)

        # Image files: route through vision pipeline
        from parser.image_parser import is_image_file
        if is_image_file(basename):
            from parser.image_parser import parse_image
            from generation.vision_provider import VisionProvider
            vision_provider = VisionProvider(
                base_url=settings.vision.ollama_base_url,
                model=settings.vision.model_name,
            )
            doc = parse_image(
                image_bytes=file_bytes,
                filename=basename,
                vision_provider=vision_provider,
                max_resolution=settings.vision.max_resolution,
                storage_uri=f"file://{file_path}",
            )
            doc.metadata["document_id"] = doc_id
            return doc

        if ext == ".pdf":
            from parser.pdf_parser import parse_pdf
            doc = parse_pdf(pdf_bytes=file_bytes, filename=basename)
        elif ext == ".docx":
            from parser.docx_parser import parse_docx
            doc = parse_docx(docx_bytes=file_bytes, filename=basename)
        elif ext == ".csv":
            from parser.csv_parser import parse_csv
            doc = parse_csv(csv_bytes=file_bytes, filename=basename)
        elif ext in (".xlsx", ".xls"):
            from parser.excel_parser import parse_excel
            doc = parse_excel(excel_bytes=file_bytes, filename=basename)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        # Attach doc_id to metadata so downstream stages have it
        doc.metadata["document_id"] = doc_id
        return doc

    def wrapped_metadata(doc: DocumentContent, file_path: str) -> DocumentContent:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        import os
        import dataclasses
        from datetime import datetime, timezone
        extracted = extract_metadata(
            document_content=doc,
            file_bytes=file_bytes,
            document_id=doc.metadata.get("document_id", job_id),
            filename=os.path.basename(file_path),
            upload_time=datetime.now(timezone.utc).isoformat(),
            storage_uri=f"file://{file_path}",
            ingestion_job_id=job_id
        )
        return DocumentContent(
            filename=doc.filename,
            text=doc.text,
            pages=doc.pages,
            page_count=doc.page_count,
            metadata={**doc.metadata, **dataclasses.asdict(extracted)}
        )

    def composed_normalizer(doc: DocumentContent) -> DocumentContent:
        doc = clean_whitespace(doc)
        doc = normalize_encoding(doc)
        doc = extract_tables(doc)
        doc = extract_images(doc)
        return segment_pages(doc)

    return IngestionOrchestrator(
        parser_fn=real_parse,
        metadata_fn=wrapped_metadata,
        normalize_fn=composed_normalizer,
        chunker_fn=chunk_document,
        entity_extractor_fn=extract_entities,
        relationship_extractor_fn=extract_relationships,
        resolver_fn=resolve_knowledge,
        graph_repository=graph_repo,
        vector_repository=vector_repo,
        embedding_provider=embedding_provider,
        status_callback=update_status
    )


def get_calculation_service() -> "CalculationService":
    """Instantiate CalculationService with SubprocessSandbox and CodeValidator."""
    from calculation.service import CalculationService
    from calculation.subprocess_sandbox import SubprocessSandboxProvider
    from calculation.validator import CodeValidator

    settings = get_settings()
    return CalculationService(
        sandbox=SubprocessSandboxProvider(),
        validator=CodeValidator(),
        timeout_seconds=5.0,
        model_name=getattr(settings, "reasoning_model", "llama3.2"),
    )


def get_calculate_tool() -> "CalculateTool":
    """Instantiate CalculateTool backed by the application CalculationService."""
    from agents.tools.calculate import CalculateTool

    return CalculateTool(get_calculation_service())


def get_vision_provider() -> "VisionProvider":
    """Instantiate VisionProvider with configured vision model (gemma3:4b)."""
    from generation.vision_provider import VisionProvider

    settings = get_settings()
    return VisionProvider(
        base_url=settings.vision.ollama_base_url,
        model=settings.vision.model_name,
    )


def get_analyze_image_tool() -> "AnalyzeImageTool":
    """Instantiate AnalyzeImageTool backed by the application VisionProvider."""
    from agents.tools.analyze_image import AnalyzeImageTool

    return AnalyzeImageTool(get_vision_provider())

