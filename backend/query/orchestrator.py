"""Query pipeline orchestrator."""

from __future__ import annotations
import logging

from retrieval.service import RetrievalService
from generation.service import GenerationService
from generation.generation_models import GenerationResult

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """Coordinates the Retrieval and Generation stages for user queries.
    
    Instantiates NO infrastructure. Dependencies are injected.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        generation_service: GenerationService,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._generation_service = generation_service

    def answer_query(self, query: str, limit: int = 5) -> GenerationResult:
        """Execute the end-to-end read path."""
        try:
            logger.info(f"Query Started: '{query}'")
            
            # 1. Retrieve deterministic context (Vector + Graph)
            context = self._retrieval_service.retrieve(query, limit=limit)
            logger.info(f"Retrieval Complete: {len(context.chunks)} chunks, {len(context.entities)} entities.")
            
            # 2. Generate reasoned answer strictly from context
            result = self._generation_service.generate_answer(context)
            logger.info("Generation Complete.")
            
            return result
            
        except Exception as e:
            logger.error(f"Query Pipeline failed: {e}")
            raise
