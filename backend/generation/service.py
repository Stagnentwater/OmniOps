"""GenerationService for orchestrating reasoning and validation."""

from __future__ import annotations
import logging

from retrieval.retrieval_models import RetrievalContext
from generation.generation_models import GenerationResult
from generation.prompt_builder import PromptBuilder
from generation.llm_provider import LLMProvider
from generation.validator import AnswerValidator


class GenerationService:
    """Orchestrates the LLM generation pipeline.
    
    Responsible for executing the PromptBuilder -> LLMProvider -> AnswerValidator
    flow without exposing internal database or retrieval implementations.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_builder: PromptBuilder | None = None,
        validator: AnswerValidator | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._validator = validator or AnswerValidator()
        self._logger = logging.getLogger(__name__)

    def generate_answer(self, context: RetrievalContext) -> GenerationResult:
        """Process the retrieval context to generate a validated answer."""
        
        # 1. Map context and build prompt string
        prompt_package, context_mapping = self._prompt_builder.build(context)
        
        try:
            # 2. Execute LLM inference (infrastructure-agnostic)
            raw_generation = self._llm_provider.generate(prompt_package)
            
            # 3. Deterministically validate output and resolve citations
            validated_answer = self._validator.validate(raw_generation, context_mapping)
            
            return GenerationResult(
                answer=validated_answer,
                raw=raw_generation,
            )
            
        except Exception as e:
            self._logger.error(f"Generation failed: {e}")
            raise
