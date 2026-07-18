"""MVP End-to-End Integration Test for the OmniOps Pipeline."""

import os
import tempfile
import unittest

# Orchestrators
from ingestion.orchestrator import IngestionOrchestrator
from query.orchestrator import QueryOrchestrator

# Core Services
from retrieval.service import RetrievalService
from generation.service import GenerationService
from generation.prompt_builder import PromptBuilder
from generation.validator import AnswerValidator
from graph.query_service import GraphQueryService

# Domain Models
from ingestion.models import DocumentContent
from ingestion.chunk_models import ChunkCollection
from ingestion.entity_models import EntityOccurrenceCollection
from ingestion.relationship_models import RelationshipOccurrenceCollection
from ingestion.resolution_models import ResolvedKnowledgePackage

# Real Pipeline Functions
# Using simple pass-through or real implementations where available without external dependencies
from ingestion.metadata import extract_metadata
from ingestion.normalizer import clean_whitespace, normalize_encoding, segment_pages, extract_tables, extract_images
from ingestion.chunker import chunk_document
from ingestion.extractor import extract_entities
from ingestion.relationship_extractor import extract_relationships
from ingestion.resolver import resolve_knowledge

# Test Doubles
from tests.test_retrieval import MockVectorRepository, MockEmbeddingProvider
from tests.test_graph_repository import InMemoryGraphRepository
from tests.test_generation import FakeLLMProvider


class TestMVPIntegration(unittest.TestCase):
    def setUp(self):
        # 1. Setup Test Doubles
        self.graph_repo = InMemoryGraphRepository()
        self.vector_repo = MockVectorRepository()
        self.embedding_provider = MockEmbeddingProvider()
        
        # We need a Fake LLM Provider that outputs a valid citation for [Context #1]
        self.llm_provider = FakeLLMProvider(
            mock_response="The main pump P-301 is located in Sector 4 and causes high pressure alerts. [Context #1]"
        )

        # 2. Setup Services
        self.graph_query_service = GraphQueryService(self.graph_repo)
        self.retrieval_service = RetrievalService(
            vector_repo=self.vector_repo,
            graph_service=self.graph_query_service,
            embedding_provider=self.embedding_provider
        )
        self.generation_service = GenerationService(
            llm_provider=self.llm_provider,
            prompt_builder=PromptBuilder(),
            validator=AnswerValidator()
        )

        # 3. Setup Orchestrators
        
        # We need a simple parser for testing
        def mock_parse(file_path: str, doc_id: str) -> DocumentContent:
            import os
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return DocumentContent(
                filename=os.path.basename(file_path),
                text=content,
                pages=(content,),
                page_count=1,
                metadata={"document_id": doc_id}
            )

        # We need to wrap metadata to read bytes properly since the signature is (doc, filepath)
        def wrapped_metadata(doc: DocumentContent, file_path: str) -> DocumentContent:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            import os
            from datetime import datetime
            extracted = extract_metadata(
                document_content=doc,
                file_bytes=file_bytes,
                document_id=doc.metadata.get("document_id", "test"),
                filename=os.path.basename(file_path),
                upload_time=datetime.utcnow().isoformat(),
                storage_uri=f"file://{file_path}",
                ingestion_job_id="job-1"
            )
            # Convert dataclass to dict to attach to DocumentContent
            import dataclasses
            new_doc = DocumentContent(
                filename=doc.filename,
                text=doc.text,
                pages=doc.pages,
                page_count=doc.page_count,
                metadata={**doc.metadata, **dataclasses.asdict(extracted)}
            )
            return new_doc

        # We need to compose normalizers
        def composed_normalizer(doc: DocumentContent) -> DocumentContent:
            doc = clean_whitespace(doc)
            doc = normalize_encoding(doc)
            doc = extract_tables(doc)
            doc = extract_images(doc)
            return segment_pages(doc)

        def wrapped_chunker(doc: DocumentContent, doc_id: str) -> ChunkCollection:
            return chunk_document(doc, doc_id)

        # Checkpoints tracker
        self.checkpoints = []
        def track_checkpoint(state: str):
            self.checkpoints.append(state)

        self.ingestion_orchestrator = IngestionOrchestrator(
            parser_fn=mock_parse,
            metadata_fn=wrapped_metadata,
            normalize_fn=composed_normalizer,
            chunker_fn=wrapped_chunker,
            entity_extractor_fn=extract_entities,
            relationship_extractor_fn=extract_relationships,
            resolver_fn=resolve_knowledge,
            graph_repository=self.graph_repo,
            vector_repository=self.vector_repo,
            embedding_provider=self.embedding_provider,
            status_callback=track_checkpoint,
        )

        self.query_orchestrator = QueryOrchestrator(
            retrieval_service=self.retrieval_service,
            generation_service=self.generation_service,
        )

    def test_end_to_end_pipeline(self):
        # 1. Create a temporary document
        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(
                "OMNIOPS MAINTENANCE REPORT\n\n"
                "The main pump P-301 is located in Sector 4. "
                "It causes high pressure alerts frequently. "
                "It is maintained by Technician Bob.\n"
            )
            file_path = f.name
            
        doc_id = "test-doc-001"

        try:
            # 2. Execute Ingestion Pipeline
            success = self.ingestion_orchestrator.run_pipeline(file_path=file_path, document_id=doc_id)
            self.assertTrue(success)
            
            # Verify Checkpoints
            expected_checkpoints = [
                "JOB_CREATED", "PARSED", "METADATA_EXTRACTED", "NORMALIZED", 
                "CHUNKED", "ENTITY_EXTRACTED", "RELATIONSHIP_EXTRACTED", 
                "KNOWLEDGE_RESOLVED", "GRAPH_PERSISTED", "VECTOR_PERSISTED", "COMPLETED"
            ]
            self.assertEqual(self.checkpoints, expected_checkpoints)
            
            # Verify Persistence
            self.assertTrue(len(self.vector_repo.upserted) > 0)
            self.assertTrue(len(self.graph_repo._nodes) > 0)
            
            # 3. Execute Query Pipeline
            query = "What causes high pressure alerts?"
            
            # We mock the search result for the vector repo since our EmbeddingProvider mock 
            # might not match the embeddings generated during ingestion.
            # We will rely on our existing Test Double behavior for vector_repo.search
            
            result = self.query_orchestrator.answer_query(query, limit=3)
            
            # Verify GenerationResult Output Contracts
            self.assertEqual(result.raw.metadata["model"], "fake-model-1")
            
            answer = result.answer
            self.assertIn("The main pump P-301 is located in Sector 4", answer.answer_text)
            
            # Verify Citations resolved correctly
            self.assertEqual(len(answer.citations), 1)
            citation = answer.citations[0]
            
            # Because the MockVectorRepository returns a deterministic "chunk-1"
            # we expect the chunk_id to map back correctly.
            self.assertEqual(citation.chunk_id, "chunk-1")

        finally:
            os.unlink(file_path)

if __name__ == "__main__":
    unittest.main()
