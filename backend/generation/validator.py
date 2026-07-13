"""AnswerValidator for deterministic citation resolution and structural validation."""

from __future__ import annotations
import re

from generation.generation_models import (
    RawGeneration,
    GeneratedAnswer,
    Citation,
)
from retrieval.retrieval_models import RetrievedChunk


class AnswerValidator:
    """Deterministically validates LLM output and resolves citations.
    
    This stage performs NO reasoning. It purely verifies structure,
    extracts [Context #N] markers using regex, checks them against
    the ContextMapping, and rejects unknown references.
    """

    # Regex to find tags like [Context #1], [Context #2], etc.
    CITATION_PATTERN = re.compile(r"\[Context #(\d+)\]")

    def validate(
        self, raw: RawGeneration, context_mapping: dict[int, RetrievedChunk]
    ) -> GeneratedAnswer:
        """Parse the raw response, resolve valid citations, and return GeneratedAnswer."""
        
        answer_text = raw.raw_response.strip()
        
        # 1. Find all Context #N references
        matches = self.CITATION_PATTERN.findall(answer_text)
        
        # 2. Resolve to Citations and deduplicate
        seen_chunks: set[str] = set()
        citations: list[Citation] = []
        
        for match in matches:
            try:
                ctx_id = int(match)
            except ValueError:
                continue
                
            chunk = context_mapping.get(ctx_id)
            if chunk:
                # Deduplicate by chunk_id
                if chunk.chunk_id not in seen_chunks:
                    seen_chunks.add(chunk.chunk_id)
                    citations.append(
                        Citation(
                            chunk_id=chunk.chunk_id,
                            document_id=chunk.document_id,
                            page_index=chunk.page_index,
                            section=chunk.section,
                            source_text=chunk.text,
                        )
                    )
            # If ctx_id is not in context_mapping, it is an hallucinated citation.
            # We silently ignore invalid/hallucinated citations to prevent false lineage.
            # Alternatively, we could raise an error depending on strictness requirements.
            
        return GeneratedAnswer(
            answer_text=answer_text,
            citations=tuple(citations)
        )
