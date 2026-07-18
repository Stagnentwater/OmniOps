"""Concrete LLM Provider for Ollama."""

from __future__ import annotations
import json
import urllib.request
import urllib.error
import logging

from generation.generation_models import PromptPackage, RawGeneration
from generation.llm_provider import LLMProvider


class OllamaLLMProvider(LLMProvider):
    """Executes reasoning tasks against a local Ollama instance."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.logger = logging.getLogger(__name__)

    def generate(self, prompt_package: PromptPackage) -> RawGeneration:
        """Construct the prompt and POST to Ollama /api/generate."""
        
        full_prompt = (
            f"System: {prompt_package.system_prompt}\n\n"
            f"Context:\n{prompt_package.formatted_context}\n\n"
            f"User: {prompt_package.user_prompt}"
        )
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            # Pass through any metadata config if needed, e.g. temperature
        }
        
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                
            return RawGeneration(
                raw_response=result.get("response", ""),
                metadata={
                    "model": result.get("model", self.model),
                    "total_duration": result.get("total_duration", 0),
                    "prompt_eval_count": result.get("prompt_eval_count", 0),
                    "eval_count": result.get("eval_count", 0),
                }
            )
        except urllib.error.URLError as e:
            self.logger.error(f"Ollama connection failed: {e}")
            raise RuntimeError(f"Failed to communicate with LLM provider: {e}") from e
