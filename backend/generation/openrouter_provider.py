"""Production-grade OpenRouter LLM Provider."""

from __future__ import annotations
import json
import logging
import urllib.request
import urllib.error
from urllib.error import HTTPError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from generation.generation_models import PromptPackage, RawGeneration
from generation.llm_provider import LLMProvider
from config.settings import OpenRouterSettings

logger = logging.getLogger(__name__)


class LLMAuthenticationError(Exception):
    """Raised for HTTP 401/403."""


class LLMRateLimitError(Exception):
    """Raised for HTTP 429."""


class LLMServerError(Exception):
    """Raised for HTTP 5xx."""


class OpenRouterLLMProvider(LLMProvider):
    """Executes reasoning tasks against OpenRouter.
    
    Features:
    - Retries transient failures with exponential backoff.
    - Suppresses secrets and raw prompts from logs.
    - Distinguishes exact failure modes for orchestrator resilience.
    """

    def __init__(self, settings: OpenRouterSettings, timeout_seconds: float = 30.0) -> None:
        self.base_url = settings.base_url.rstrip("/")
        self.api_key = settings.api_key
        self.model = settings.model
        self.timeout = timeout_seconds

    def _should_retry(exception: BaseException) -> bool:
        """Only retry rate limits and server errors."""
        return isinstance(exception, (LLMRateLimitError, LLMServerError))

    @retry(
        retry=retry_if_exception_type((LLMRateLimitError, LLMServerError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def generate(self, prompt_package: PromptPackage) -> RawGeneration:
        """Construct the prompt and execute the HTTP call to OpenRouter."""
        
        endpoint = f"{self.base_url}/chat/completions"
        
        # Format as OpenAI Chat Completion array
        messages = [
            {"role": "system", "content": prompt_package.system_prompt},
            {"role": "user", "content": f"Context:\n{prompt_package.formatted_context}\n\nQuestion: {prompt_package.user_prompt}"}
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://omniops.internal", # Required by OpenRouter
            "X-Title": "OmniOps"
        }
        
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                # Extract content
                choices = result.get("choices", [])
                if not choices:
                    raise ValueError("Malformed response: missing 'choices'")
                
                content = choices[0].get("message", {}).get("content", "")
                
                # Extract metadata
                usage = result.get("usage", {})
                metadata = {
                    "model": result.get("model", self.model),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
                
                return RawGeneration(raw_response=content, metadata=metadata)

        except HTTPError as e:
            if e.code in (401, 403):
                logger.error("OpenRouter authentication failed.")
                raise LLMAuthenticationError("Authentication failed check API key.") from e
            elif e.code == 429:
                logger.warning("OpenRouter rate limit exceeded. Retrying...")
                raise LLMRateLimitError("Rate limit exceeded.") from e
            elif 500 <= e.code < 600:
                logger.warning(f"OpenRouter server error {e.code}. Retrying...")
                raise LLMServerError(f"Server error {e.code}") from e
            else:
                logger.error(f"OpenRouter HTTP Error {e.code}.")
                raise RuntimeError(f"Unexpected HTTP Error {e.code}") from e
        except urllib.error.URLError as e:
            logger.error("OpenRouter connection failed.")
            raise LLMServerError(f"Connection failed: {e.reason}") from e
