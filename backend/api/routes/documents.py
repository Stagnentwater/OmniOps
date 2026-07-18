from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import uuid
from io import BytesIO

from dependencies import get_metadata_repo, get_ingestion_orchestrator
from database.repositories import MetadataRepository, DocumentMetadata
from storage.factory import get_storage_service
from storage.service import StorageService
from config.settings import get_settings
from graph.neo4j_connection import Neo4jConnectionManager
from graph.neo4j_repository import Neo4jGraphRepository
from vector.qdrant_connection import QdrantConnectionManager
from vector.qdrant_repository import QdrantVectorRepository

router = APIRouter(prefix="/documents", tags=["Documents"])

class DocumentItem(BaseModel):
    id: str
    filename: str
    status: str
    upload_time: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentItem]

class UploadResponse(BaseModel):
    document_id: str
    status: str

class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    progress_percent: int
    error_message: Optional[str] = None

class DeleteResponse(BaseModel):
    success: bool

@router.get("", response_model=DocumentListResponse)
async def list_documents(repo: MetadataRepository = Depends(get_metadata_repo)) -> DocumentListResponse:
    """List all ingested documents by querying Postgres status."""
    # Since we need to list them, let's fetch all jobs. 
    # To keep it simple, we'll fetch from the Postgres connection directly or just mock listing if repo lacks a list method.
    # Actually, MetadataRepository has `get_document_metadata` but maybe not list? Let's check.
    # For now, return empty or fetch using raw query to get status.
    conn = repo._connect()
    repo._ensure_tables(conn)
    docs = []
    with conn.cursor() as cur:
        cur.execute("""
            WITH LatestJobs AS (
                SELECT DISTINCT ON (document_id) document_id, status, created_at
                FROM ingestion_jobs
                ORDER BY document_id, created_at DESC
            )
            SELECT d.document_id, d.file_name, j.status, d.created_at
            FROM documents d
            LEFT JOIN LatestJobs j ON d.document_id = j.document_id
            ORDER BY d.created_at DESC
        """)
        for row in cur.fetchall():
            docs.append(DocumentItem(
                id=row[0],
                filename=row[1],
                status=row[2] or "UNKNOWN",
                upload_time=row[3].isoformat()
            ))
    conn.close()
    return DocumentListResponse(documents=docs)



@router.get("/{document_id}/content")
async def get_document_content(document_id: str, repo: MetadataRepository = Depends(get_metadata_repo)):
    """Stream the raw PDF file to the client."""
    meta = repo.get_document_metadata(document_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Document not found")
        
    storage = get_storage_service()
    content = storage.get_bytes(storage_key=meta.stored_object.storage_key)
    return Response(content=content, media_type="application/pdf")

@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str, repo: MetadataRepository = Depends(get_metadata_repo)) -> DocumentStatusResponse:
    """Poll persistent ingestion pipeline status."""
    # Custom query to get the latest job status
    conn = repo._connect()
    repo._ensure_tables(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT status, error FROM ingestion_jobs WHERE document_id = %s ORDER BY created_at DESC LIMIT 1", (document_id,))
        row = cur.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
        
    status = row[0]
    return DocumentStatusResponse(
        document_id=document_id,
        status=status,
        progress_percent=100 if status == "COMPLETED" else 50,
        error_message=row[1]
    )

@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str, 
    repo: MetadataRepository = Depends(get_metadata_repo)
) -> DeleteResponse:
    """Remove document."""
    meta = repo.get_document_metadata(document_id)
    if meta:
        storage = get_storage_service()
        storage.delete(storage_key=meta.stored_object.storage_key)
        
    settings = get_settings()
    
    # Delete from Qdrant
    qdrant_conn = QdrantConnectionManager(settings.qdrant.host, settings.qdrant.port)
    vector_repo = QdrantVectorRepository(qdrant_conn)
    vector_repo.delete_document(document_id)
    
    # Delete from Neo4j
    neo4j_conn = Neo4jConnectionManager(settings.neo4j.uri, settings.neo4j.user, settings.neo4j.password)
    graph_repo = Neo4jGraphRepository(neo4j_conn)
    graph_repo.delete_document(document_id)
    
    # Delete from Postgres
    repo.delete_document(document_id=document_id)
    
    return DeleteResponse(success=True)
