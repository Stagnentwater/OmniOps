"""Immutable contracts for the Generation Layer."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromptPackage:
    """Immutable string payload sent to the LLM."""
    
    system_prompt: str
    user_prompt: str
    formatted_context: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Citation:
    """Strict evidence lineage for a generated statement."""
    
    chunk_id: str
    document_id: str
    page_index: int
    section: str | None
    source_text: str


@dataclass(frozen=True)
class GeneratedAnswer:
    """The final validated reasoning and its true evidence."""
    
    answer_text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class RawGeneration:
    """The unvalidated raw output from the LLM.
    
    Agnostic to the infrastructure provider (e.g. OpenAI, Ollama).
    """
    
    raw_response: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class GenerationResult:
    """The final pipeline output after validation."""
    
    answer: GeneratedAnswer
    raw: RawGeneration
