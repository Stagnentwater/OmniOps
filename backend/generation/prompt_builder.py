"""PromptBuilder for formatting RetrievalContext into string payloads."""

from __future__ import annotations
from typing import Any

from retrieval.retrieval_models import RetrievalContext, RetrievedChunk
from generation.generation_models import PromptPackage


class PromptBuilder:
    """Formats RetrievalContext into an LLM-ready PromptPackage.
    
    Responsible for masking internal identifiers with temporary Context #N
    labels to ensure the LLM never sees internal UUIDs or document IDs.
    """

    def __init__(self, system_prompt_template: str | None = None) -> None:
        self._system_prompt = system_prompt_template or (
            "You are a helpful industrial intelligence assistant. "
            "Use the provided context to answer the user's query. "
            "If the answer is not in the context, say 'I do not know'. "
            "Always cite your sources using the format [Context #N] at the end of the sentence."
        )

    def build(self, context: RetrievalContext) -> tuple[PromptPackage, dict[int, RetrievedChunk]]:
        """Map chunks to Context #N and build the formatted prompt string.
        
        Returns:
            A tuple of (PromptPackage, ContextMapping).
            The ContextMapping maps the integer N back to the original RetrievedChunk.
        """
        
        context_mapping: dict[int, RetrievedChunk] = {}
        formatted_blocks: list[str] = []
        
        # 1. Format chunks
        for idx, chunk in enumerate(context.chunks, start=1):
            context_mapping[idx] = chunk
            
            block = f"--- Context #{idx} ---\n"
            if chunk.section:
                block += f"Section: {chunk.section}\n"
            block += f"Text:\n{chunk.text}\n"
            
            formatted_blocks.append(block)
            
        # 2. Format Graph Entities (Optional structural context)
        # Note: We do not map entities to citations currently as chunks hold the verbatim text,
        # but we can provide structural context for reasoning.
        if context.entities or context.relationships:
            formatted_blocks.append("--- Structural Knowledge Graph ---")
            for ent in context.entities:
                formatted_blocks.append(f"Entity: {ent.canonical_name} ({ent.entity_type})")
            for rel in context.relationships:
                # Resolve names if possible (requires a lookup map, simplified here)
                formatted_blocks.append(f"Relationship: {rel.source_id} -> {rel.relationship_type} -> {rel.target_id}")

        formatted_context_str = "\n".join(formatted_blocks)
        
        package = PromptPackage(
            system_prompt=self._system_prompt,
            user_prompt=context.query,
            formatted_context=formatted_context_str,
            metadata={"num_contexts": len(context_mapping)}
        )
        
        return package, context_mapping
