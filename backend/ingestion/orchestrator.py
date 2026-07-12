"""Ingestion orchestrator job and modular stage functions for MVP."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from time import perf_counter
from typing import Callable, TypeVar

from ingestion.models import DocumentContent


logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class StructuredDocument:
    """Document understanding output."""

    document_id: str
    sections: list[str]


@dataclass(frozen=True)
class KnowledgePackage:
    """Knowledge extraction output."""

    document_id: str
    entities: list[str]
    relationships: list[str]


@dataclass(frozen=True)
class NormalizedKnowledgePackage:
    """Knowledge normalization output."""

    document_id: str
    entities: list[str]
    relationships: list[str]


@dataclass(frozen=True)
class ResolvedKnowledgePackage:
    """Knowledge resolution output."""

    document_id: str
    entities: list[str]
    relationships: list[str]
    confidence: float


@dataclass(frozen=True)
class ValidatedKnowledgePackage:
    """Knowledge validation output."""

    document_id: str
    entities: list[str]
    relationships: list[str]
    confidence: float
    valid: bool


@dataclass(frozen=True)
class PersistedKnowledge:
    """Persistence output after graph and vector upserts."""

    document_id: str
    graph_complete: bool
    vector_complete: bool


def _emit_stage_log(
    *,
    job_id: str,
    document_id: str,
    stage: str,
    status: str,
    duration_ms: int,
    error: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "job_id": job_id,
        "document_id": document_id,
        "stage": stage,
        "status": status,
        "duration_ms": duration_ms,
        "error": error,
    }
    logger.info("%s", json.dumps(payload))


def _timed_stage(
    *,
    job_id: str,
    document_id: str,
    stage: str,
    fn: Callable[[], T],
) -> T:
    start = perf_counter()
    try:
        result = fn()
    except Exception as exc:
        duration_ms = int((perf_counter() - start) * 1000)
        _emit_stage_log(
            job_id=job_id,
            document_id=document_id,
            stage=stage,
            status="FAILED",
            duration_ms=duration_ms,
            error=str(exc),
        )
        raise
    duration_ms = int((perf_counter() - start) * 1000)
    _emit_stage_log(
        job_id=job_id,
        document_id=document_id,
        stage=stage,
        status="COMPLETED",
        duration_ms=duration_ms,
    )
    return result


def parse_document(*, document_id: str, file_name: str) -> DocumentContent:
    """Parse a source document into raw textual content."""
    return DocumentContent(document_id=document_id, text=f"parsed::{file_name}")


def understand_document(content: DocumentContent) -> StructuredDocument:
    """Build a structured document representation from parsed content."""
    return StructuredDocument(document_id=content.document_id, sections=[content.text])


def extract_knowledge(structured: StructuredDocument) -> KnowledgePackage:
    """Extract entities and relations from structured document data."""
    return KnowledgePackage(
        document_id=structured.document_id,
        entities=["asset:sample"],
        relationships=["asset:sample-HAS_COMPONENT-component:sample"],
    )


def normalize_knowledge(package: KnowledgePackage) -> NormalizedKnowledgePackage:
    """Normalize extracted entities and relationships."""
    return NormalizedKnowledgePackage(
        document_id=package.document_id,
        entities=package.entities,
        relationships=package.relationships,
    )


def resolve_knowledge(package: NormalizedKnowledgePackage) -> ResolvedKnowledgePackage:
    """Resolve conflicts and assign confidence for normalized knowledge."""
    return ResolvedKnowledgePackage(
        document_id=package.document_id,
        entities=package.entities,
        relationships=package.relationships,
        confidence=0.95,
    )


def validate_knowledge(package: ResolvedKnowledgePackage) -> ValidatedKnowledgePackage:
    """Validate resolved knowledge before persistence."""
    return ValidatedKnowledgePackage(
        document_id=package.document_id,
        entities=package.entities,
        relationships=package.relationships,
        confidence=package.confidence,
        valid=True,
    )


def upsert_graph(package: ValidatedKnowledgePackage) -> bool:
    """Upsert graph knowledge in Neo4j (placeholder for MVP queue verification)."""
    return package.valid


def upsert_vector(package: ValidatedKnowledgePackage, fail_vector_upsert: bool) -> bool:
    """Upsert vectors in Qdrant (placeholder for MVP queue verification)."""
    if fail_vector_upsert:
        raise RuntimeError("Simulated vector upsert failure")
    return package.valid


def process_ingestion_job(
    *,
    lifecycle_job_id: str,
    document_id: str,
    file_name: str,
    fail_vector_upsert: bool = False,
) -> dict[str, object]:
    """Run the orchestrated ingestion pipeline with modular stages."""
    from rq import get_current_job
    from database.repositories import MetadataRepository

    repository = MetadataRepository()
    rq_job = get_current_job()
    job_id = rq_job.id if rq_job is not None else lifecycle_job_id
    overall_start = perf_counter()
    repository.update_job_status(job_id=lifecycle_job_id, status="PROCESSING")

    try:
        parsed = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="PARSING",
            fn=lambda: parse_document(document_id=document_id, file_name=file_name),
        )
        understood = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="UNDERSTANDING",
            fn=lambda: understand_document(parsed),
        )
        extracted = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="EXTRACTING",
            fn=lambda: extract_knowledge(understood),
        )
        normalized = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="NORMALIZING",
            fn=lambda: normalize_knowledge(extracted),
        )
        resolved = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="RESOLVING",
            fn=lambda: resolve_knowledge(normalized),
        )
        validated = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="VALIDATING",
            fn=lambda: validate_knowledge(resolved),
        )
        graph_complete = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="GRAPH_UPSERT",
            fn=lambda: upsert_graph(validated),
        )
        repository.update_job_status(job_id=lifecycle_job_id, status="GRAPH_COMPLETE")
        vector_complete = _timed_stage(
            job_id=job_id,
            document_id=document_id,
            stage="VECTOR_UPSERT",
            fn=lambda: upsert_vector(validated, fail_vector_upsert=fail_vector_upsert),
        )
        repository.update_job_status(job_id=lifecycle_job_id, status="VECTOR_COMPLETE")
    except Exception as exc:
        repository.update_job_status(job_id=lifecycle_job_id, status="FAILED", error=str(exc))
        raise
    persisted = PersistedKnowledge(
        document_id=document_id,
        graph_complete=graph_complete,
        vector_complete=vector_complete,
    )
    duration_ms = int((perf_counter() - overall_start) * 1000)
    _emit_stage_log(
        job_id=job_id,
        document_id=document_id,
        stage="INGESTION_TOTAL",
        status="COMPLETED",
        duration_ms=duration_ms,
    )
    repository.update_job_status(job_id=lifecycle_job_id, status="COMPLETED")
    return {
        "job_id": lifecycle_job_id,
        "document_id": persisted.document_id,
        "graph_complete": persisted.graph_complete,
        "vector_complete": persisted.vector_complete,
        "status": "COMPLETED",
        "duration_ms": duration_ms,
    }
