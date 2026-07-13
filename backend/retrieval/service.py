"""RetrievalService for merging semantic and structural context."""

from __future__ import annotations
import concurrent.futures
import logging

from vector.repository import VectorRepository
from vector.embedding_provider import EmbeddingProvider
from graph.query_service import GraphQueryService
from retrieval.retrieval_models import (
    RetrievalContext,
    RetrievedChunk,
    RetrievedEntity,
    RetrievedRelationship,
)


class RetrievalService:
    """Orchestrates parallel independent retrieval from Vector and Graph layers.
    
    This service purely retrieves, deduplicates, and orders deterministic data.
    It does not perform NLP, entity extraction, or score fusion.
    """

    def __init__(
        self,
        vector_repo: VectorRepository,
        graph_service: GraphQueryService,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._vector_repo = vector_repo
        self._graph_service = graph_service
        self._embedding_provider = embedding_provider
        self._logger = logging.getLogger(__name__)

    def retrieve(self, query: str, limit: int = 5) -> RetrievalContext:
        """Execute independent parallel retrievals and merge evidence."""
        
        # We will use ThreadPoolExecutor to run vector and graph queries in parallel
        # to guarantee independence as required by the architecture.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            vector_future = executor.submit(self._retrieve_vectors, query, limit)
            graph_future = executor.submit(self._retrieve_graph, query, limit)
            
            chunks = vector_future.result()
            entities, relationships = graph_future.result()

        return RetrievalContext(
            query=query,
            chunks=tuple(chunks),
            entities=tuple(entities),
            relationships=tuple(relationships),
        )

    def _retrieve_vectors(self, query: str, limit: int) -> list[RetrievedChunk]:
        """Generate embedding and query Qdrant."""
        try:
            embeddings = self._embedding_provider.generate_embeddings([query])
            if not embeddings:
                return []
            
            query_vector = embeddings[0]
            search_results = self._vector_repo.search(query_vector, limit=limit)
            
            # Deduplicate by chunk_id and map to RetrievedChunk
            seen_chunks: set[str] = set()
            retrieved_chunks: list[RetrievedChunk] = []
            
            for res in search_results:
                if res.chunk_id not in seen_chunks:
                    seen_chunks.add(res.chunk_id)
                    retrieved_chunks.append(
                        RetrievedChunk(
                            chunk_id=res.chunk_id,
                            document_id=res.document_id,
                            text=res.text,
                            score=res.score,
                            page_index=res.page_index,
                            section=res.section,
                            metadata=res.metadata,
                        )
                    )
            return retrieved_chunks
        except Exception as e:
            self._logger.error(f"Vector retrieval failed: {e}")
            return []

    def _retrieve_graph(self, query: str, limit: int) -> tuple[list[RetrievedEntity], list[RetrievedRelationship]]:
        """Query Neo4j directly using raw text (no NLP entity extraction)."""
        try:
            # 1. Keyword search on nodes
            nodes = self._graph_service.search_nodes(query, limit=limit)
            
            seen_entities: set[str] = set()
            retrieved_entities: list[RetrievedEntity] = []
            
            for n_props in nodes:
                e_id = n_props.get("entity_id")
                if e_id and e_id not in seen_entities:
                    seen_entities.add(e_id)
                    retrieved_entities.append(
                        RetrievedEntity(
                            entity_id=e_id,
                            entity_type=n_props.get("entity_type", "Unknown"),
                            canonical_name=n_props.get("canonical_name", "Unknown"),
                            properties=n_props,
                        )
                    )
                    
            # 2. Expand subgraph for discovered entities to get context relationships
            seen_rels: set[tuple[str, str, str]] = set()
            retrieved_rels: list[RetrievedRelationship] = []
            
            for entity in retrieved_entities:
                # We do a shallow expansion (depth=1) to keep context relevant
                subgraph = self._graph_service.expand_subgraph(entity.entity_id, max_depth=1)
                
                # Add connected nodes we might not have seen
                for n_props in subgraph.get("nodes", []):
                    e_id = n_props.get("entity_id")
                    if e_id and e_id not in seen_entities:
                        seen_entities.add(e_id)
                        retrieved_entities.append(
                            RetrievedEntity(
                                entity_id=e_id,
                                entity_type=n_props.get("entity_type", "Unknown"),
                                canonical_name=n_props.get("canonical_name", "Unknown"),
                                properties=n_props,
                            )
                        )
                
                # Add relationships
                for edge in subgraph.get("edges", []):
                    src = edge.get("source_entity_id")
                    tgt = edge.get("target_entity_id")
                    rel_type = edge.get("relationship_type")
                    
                    if src and tgt and rel_type:
                        rel_signature = (src, rel_type, tgt)
                        if rel_signature not in seen_rels:
                            seen_rels.add(rel_signature)
                            retrieved_rels.append(
                                RetrievedRelationship(
                                    source_id=src,
                                    target_id=tgt,
                                    relationship_type=rel_type,
                                    properties=edge,
                                )
                            )
                            
            return retrieved_entities, retrieved_rels
            
        except Exception as e:
            self._logger.error(f"Graph retrieval failed: {e}")
            return [], []
