"""Vision LLM provider for image understanding via Ollama.

Uses the Ollama /api/chat endpoint with base64-encoded images.
This is separate from the text-based OllamaLLMProvider because
vision tasks use a different API shape (chat messages with images)
and a different model (e.g., gemma3:4b vs llama3.2).
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VisionResult:
    """Output from vision model inference on a single image."""

    text: str
    model: str
    total_duration_ns: int
    eval_count: int


class VisionProvider:
    """Sends images to a local Ollama vision model for understanding.

    Uses /api/chat with base64-encoded images. The model must already
    be pulled via `ollama pull <model>` before first use.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gemma3:4b",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def describe_image(
        self,
        image_bytes: bytes,
        prompt: str = (
            "Describe this image thoroughly. "
            "If it shows industrial or refinery equipment, identify components, labels, gauges, and conditions. "
            "If it is a general, cartoon, meme, animal, person, or non-refinery image, describe what is depicted "
            "in detail (characters, objects, actions, setting, colors, text) and note that it is non-industrial."
        ),
    ) -> VisionResult:
        """Send an image to the vision model and get a text description.

        Args:
            image_bytes: Raw bytes of the image file.
            prompt: The text prompt to send with the image.

        Returns:
            A VisionResult containing the model's text output.

        Raises:
            RuntimeError: If the Ollama API call fails.
        """
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [encoded_image],
                }
            ],
            "stream": False,
        }

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.error("Ollama vision call failed: %s", e)
            raise RuntimeError(
                f"Failed to communicate with vision model at {self._base_url}: {e}"
            ) from e

        message = result.get("message", {})
        text = message.get("content", "")

        return VisionResult(
            text=text,
            model=result.get("model", self._model),
            total_duration_ns=result.get("total_duration", 0),
            eval_count=result.get("eval_count", 0),
        )

    def classify_image(self, image_bytes: bytes) -> str:
        """Classify an image into one of the predefined categories.

        Returns one of: PID, PHOTOGRAPH, DIAGRAM, SCREENSHOT, SCANNED_DOCUMENT

        Args:
            image_bytes: Raw bytes of the image file.

        Returns:
            A classification label string.
        """
        classification_prompt = (
            "Classify this image into exactly one of the following categories:\n"
            "PID, PHOTOGRAPH, DIAGRAM, SCREENSHOT, SCANNED_DOCUMENT\n\n"
            "PID means Piping and Instrumentation Diagram or process flow diagram.\n"
            "PHOTOGRAPH means a real-world photo of equipment or facilities.\n"
            "DIAGRAM means a technical drawing, chart, or schematic that is not a P&ID.\n"
            "SCREENSHOT means a computer screen capture.\n"
            "SCANNED_DOCUMENT means a scanned paper document or form.\n\n"
            "Respond with ONLY the classification label, nothing else."
        )

        result = self.describe_image(image_bytes, prompt=classification_prompt)
        raw_label = result.text.strip().upper().replace(" ", "_")

        valid_labels = {
            "PID", "PHOTOGRAPH", "DIAGRAM", "SCREENSHOT", "SCANNED_DOCUMENT",
        }

        # Fuzzy match — the model may return slight variations
        for label in valid_labels:
            if label in raw_label:
                return label

        logger.warning(
            "Vision model returned unrecognized classification '%s', defaulting to PHOTOGRAPH.",
            raw_label,
        )
        return "PHOTOGRAPH"
