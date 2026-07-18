"""Ingestion orchestrator job and modular stage functions for MVP."""

from __future__ import annotations

import logging
from typing import Any, Callable

from ingestion.models import DocumentContent
from ingestion.chunk_models import ChunkCollection
from ingestion.entity_models import EntityOccurrenceCollection
from ingestion.relationship_models import RelationshipOccurrenceCollection
from ingestion.resolution_models import ResolvedKnowledgePackage
from graph.repository import GraphRepository
from vector.repository import VectorRepository
from vector.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """Pure coordinator for the MVP ingestion pipeline.
    
    Instantiates NO infrastructure. All dependencies are injected.
    Exposes deterministic checkpoints.
    """

    def __init__(
        self,
        parser_fn: Callable[[str, str], DocumentContent],
        metadata_fn: Callable[[DocumentContent, str], DocumentContent],
        normalize_fn: Callable[[DocumentContent], DocumentContent],
        chunker_fn: Callable[[DocumentContent, str], ChunkCollection],
        entity_extractor_fn: Callable[[ChunkCollection], EntityOccurrenceCollection],
        relationship_extractor_fn: Callable[[EntityOccurrenceCollection, ChunkCollection], RelationshipOccurrenceCollection],
        resolver_fn: Callable[[EntityOccurrenceCollection, RelationshipOccurrenceCollection], ResolvedKnowledgePackage],
        graph_repository: GraphRepository,
        vector_repository: VectorRepository,
        embedding_provider: EmbeddingProvider,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._parser = parser_fn
        self._metadata = metadata_fn
        self._normalize = normalize_fn
        self._chunker = chunker_fn
        self._extract_entities = entity_extractor_fn
        self._extract_relationships = relationship_extractor_fn
        self._resolve = resolver_fn
        self._graph_repo = graph_repository
        self._vector_repo = vector_repository
        self._embedding_provider = embedding_provider
        
        # Callback for updating job status (e.g., to a DB)
        self._status_callback = status_callback or (lambda state: None)

    def _update_state(self, state: str) -> None:
        """Deterministic checkpoint emitter."""
        logger.info(f"Pipeline Checkpoint: {state}")
        self._status_callback(state)

    def run_pipeline(self, file_path: str, document_id: str) -> bool:
        """Execute the end-to-end DAG."""
        import traceback
        import time

        try:
            logger.info(f"Starting ingestion pipeline for document_id={document_id}")
            self._update_state("JOB_CREATED")
            
            # 1. Parsing
            logger.info(f"[{document_id}] Stage 1: Parsing PDF...")
            t0 = time.time()
            doc_content = self._parser(file_path, document_id)
            logger.info(f"[{document_id}] Stage 1 Complete ({(time.time()-t0):.2f}s). Parsed {doc_content.page_count} pages.")
            self._update_state("PARSED")
            
            # 2. Metadata Extraction
            logger.info(f"[{document_id}] Stage 2: Extracting metadata...")
            t0 = time.time()
            doc_content = self._metadata(doc_content, file_path)
            logger.info(f"[{document_id}] Stage 2 Complete ({(time.time()-t0):.2f}s). Metadata keys: {list(doc_content.metadata.keys())}")
            self._update_state("METADATA_EXTRACTED")
            
            # 3. Normalization
            logger.info(f"[{document_id}] Stage 3: Normalizing document content...")
            t0 = time.time()
            doc_content = self._normalize(doc_content)
            logger.info(f"[{document_id}] Stage 3 Complete ({(time.time()-t0):.2f}s).")
            self._update_state("NORMALIZED")
            
            # 4. Chunking
            logger.info(f"[{document_id}] Stage 4: Chunking document...")
            t0 = time.time()
            chunks = self._chunker(doc_content, document_id)
            logger.info(f"[{document_id}] Stage 4 Complete ({(time.time()-t0):.2f}s). Created {len(chunks.chunks)} chunks.")
            self._update_state("CHUNKED")
            
            # 5. Entity Extraction
            logger.info(f"[{document_id}] Stage 5: Extracting entities...")
            t0 = time.time()
            entities = self._extract_entities(chunks)
            logger.info(f"[{document_id}] Stage 5 Complete ({(time.time()-t0):.2f}s). Found {len(entities.occurrences)} entities.")
            self._update_state("ENTITY_EXTRACTED")
            
            # 6. Relationship Extraction
            logger.info(f"[{document_id}] Stage 6: Extracting relationships...")
            t0 = time.time()
            relationships = self._extract_relationships(entities, chunks)
            logger.info(f"[{document_id}] Stage 6 Complete ({(time.time()-t0):.2f}s). Found {len(relationships.relationships)} relationships.")
            self._update_state("RELATIONSHIP_EXTRACTED")
            
            # 7. Knowledge Resolution
            logger.info(f"[{document_id}] Stage 7: Resolving knowledge graph nodes and edges...")
            t0 = time.time()
            resolved_pkg = self._resolve(entities, relationships)
            logger.info(f"[{document_id}] Stage 7 Complete ({(time.time()-t0):.2f}s). Resolved {len(resolved_pkg.resolved_entities)} nodes and {len(resolved_pkg.resolved_relationships)} edges.")
            self._update_state("KNOWLEDGE_RESOLVED")
            
            # 8. Graph Persistence
            logger.info(f"[{document_id}] Stage 8: Persisting graph to Neo4j...")
            t0 = time.time()
            self._graph_repo.persist_knowledge_package(resolved_pkg)
            logger.info(f"[{document_id}] Stage 8 Complete ({(time.time()-t0):.2f}s).")
            self._update_state("GRAPH_PERSISTED")
            
            # 9. Vector Persistence
            logger.info(f"[{document_id}] Stage 9: Persisting vectors to Qdrant...")
            t0 = time.time()
            texts_to_embed = [chunk.text for chunk in chunks.chunks]
            if texts_to_embed:
                logger.info(f"[{document_id}] Generating embeddings for {len(texts_to_embed)} texts...")
                embeddings = self._embedding_provider.generate_embeddings(texts_to_embed)
                logger.info(f"[{document_id}] Upserting chunks to Qdrant...")
                self._vector_repo.upsert_chunks(chunks, embeddings)
            logger.info(f"[{document_id}] Stage 9 Complete ({(time.time()-t0):.2f}s).")
            self._update_state("VECTOR_PERSISTED")
            
            logger.info(f"[{document_id}] Pipeline successfully completed end-to-end.")
            self._update_state("COMPLETED")
            return True
            
        except Exception as e:
            logger.error(f"[{document_id}] Pipeline failed at current stage with exception: {str(e)}")
            logger.error(f"[{document_id}] Traceback:\n{traceback.format_exc()}")
            try:
                self._update_state("FAILED")
            except Exception as update_err:
                logger.error(f"[{document_id}] Failed to update status to FAILED: {str(update_err)}")
            raise

def process_ingestion_job(lifecycle_job_id: str, document_id: str, file_name: str) -> None:
    """Entry point for the RQ worker to process an ingestion job."""
    from dependencies import get_ingestion_orchestrator
    from config.settings import get_settings
    from pathlib import Path
    import os
    
    settings = get_settings()
    safe_name = Path(file_name).name
    storage_key = f"documents/{document_id}/{safe_name}"
    file_path = os.path.join(settings.storage.local_root, storage_key)
    
    orchestrator = get_ingestion_orchestrator(job_id=lifecycle_job_id)
    orchestrator.run_pipeline(file_path=file_path, document_id=document_id)

