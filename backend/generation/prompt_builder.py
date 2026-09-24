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
            "If the user's query is just a topic or name (like a pump name), summarize all the information you have about it from the context. "
            "If you truly cannot find any relevant information in the context, say 'I do not know'. "
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
            
            # Create a lookup map to translate raw hashes to human-readable names
            entity_map = {ent.entity_id: ent.canonical_name for ent in context.entities}
            
            for ent in context.entities:
                formatted_blocks.append(f"Entity: {ent.canonical_name} ({ent.entity_type})")
                
            for rel in context.relationships:
                src_name = entity_map.get(rel.source_id, rel.source_id)
                tgt_name = entity_map.get(rel.target_id, rel.target_id)
                formatted_blocks.append(f"Relationship: {src_name} -> {rel.relationship_type} -> {tgt_name}")

        formatted_context_str = "\n".join(formatted_blocks)
        
        package = PromptPackage(
            system_prompt=self._system_prompt,
            user_prompt=context.query,
            formatted_context=formatted_context_str,
            metadata={"num_contexts": len(context_mapping)}
        )
        
        return package, context_mapping
