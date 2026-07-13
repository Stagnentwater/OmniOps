"""Abstract interface for LLM execution."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from generation.generation_models import PromptPackage, RawGeneration


class LLMProvider(ABC):
    """Abstract interface for executing prompts against an LLM.
    
    The generation orchestration layer depends exclusively on this interface,
    allowing seamless swapping between OpenAI, Ollama, Gemini, etc.
    """

    @abstractmethod
    def generate(self, prompt_package: PromptPackage) -> RawGeneration:
        """Execute the prompt and return the unvalidated raw string."""
        pass
