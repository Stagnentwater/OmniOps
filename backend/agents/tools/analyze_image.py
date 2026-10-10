"""AnalyzeImage tool for visual inspection and understanding.

Wraps VisionProvider to give the agent access to the local Gemma 3 4B
vision model for inspecting equipment photographs, P&ID diagrams,
scanned maintenance documents, and reading gauges/nameplates.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult
from generation.vision_provider import VisionProvider, VisionResult

logger = logging.getLogger(__name__)


class AnalyzeImageResult(str):
    """String result that also preserves vision inference metadata."""

    raw_text: str
    model: str
    eval_count: int

    def __new__(
        cls,
        content: str,
        raw_text: str = "",
        model: str = "gemma3:4b",
        eval_count: int = 0,
    ) -> AnalyzeImageResult:
        obj = super().__new__(cls, content)
        obj.raw_text = raw_text
        obj.model = model
        obj.eval_count = eval_count
        return obj


class AnalyzeImageTool(Tool):
    """Agent tool for visual understanding of industrial images."""

    def __init__(
        self,
        vision_provider: VisionProvider,
    ) -> None:
        """Initialize the AnalyzeImage tool.

        Args:
            vision_provider: Configured VisionProvider instance (defaulting to gemma3:4b).
        """
        self._vision_provider = vision_provider

    @property
    def definition(self) -> ToolDefinition:
        """Return the tool schema for LLM tool selection."""
        return ToolDefinition(
            name="analyze_image",
            description=(
                "Analyzes industrial images, equipment photographs, engineering diagrams, "
                "or scanned documents using the local vision model (gemma3:4b). "
                "Can describe visible components, read gauges, transcribe text from labels, "
                "or classify the image type. Use this tool when visual analysis is needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the image file on disk to analyze.",
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Optional raw base64 encoded image content if file path is not available.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": (
                            "Specific question or inspection instruction for the vision model "
                            "(e.g., 'What is the pressure reading on the gauge?' or "
                            "'List all equipment labels in this diagram')."
                        ),
                    },
                    "task": {
                        "type": "string",
                        "enum": ["describe", "classify"],
                        "description": (
                            "Analysis task: 'describe' (default) for detailed visual explanation, "
                            "or 'classify' for categorizing image into PID, PHOTOGRAPH, DIAGRAM, etc."
                        ),
                    },
                },
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute image analysis with the vision provider.

        Args:
            arguments: Dictionary with 'image_path' or 'image_base64', and optional 'prompt', 'task'.

        Returns:
            ToolResult containing vision description or error details.
        """
        if not isinstance(arguments, dict):
            return ToolResult(
                tool_name="analyze_image",
                success=False,
                result=None,
                error="Arguments must be a dictionary.",
            )

        image_path = arguments.get("image_path")
        image_base64 = arguments.get("image_base64")
        prompt = arguments.get("prompt")
        task = arguments.get("task", "describe")

        # Load image bytes
        image_bytes: bytes | None = None
        if isinstance(image_base64, str) and image_base64.strip():
            try:
                image_bytes = base64.b64decode(image_base64.strip())
            except Exception as e:
                return ToolResult(
                    tool_name="analyze_image",
                    success=False,
                    result=None,
                    error=f"Invalid base64 image data: {e}",
                )
        elif isinstance(image_path, str) and image_path.strip():
            clean_path = image_path.strip()
            # Normalize file URI if passed
            if clean_path.startswith("file://"):
                clean_path = clean_path[7:]
            clean_path = clean_path.replace(r"\&", "&")
            if not os.path.isfile(clean_path):
                # Try cross-platform path normalization
                # 1. Windows path on Linux (e.g. D:\data\storage -> /data/storage)
                import re
                alt1 = re.sub(r"^[A-Za-z]:[\\/]", "/", clean_path).replace("\\", "/")
                # 2. Linux path on Windows (e.g. /data/storage -> D:\data\storage)
                alt2 = os.path.abspath(clean_path)
                from config.settings import get_settings
                local_root = os.path.abspath(get_settings().storage.local_root)
                alt3 = os.path.join(local_root, os.path.basename(clean_path))
                alt4 = clean_path.replace("/data/storage", local_root).replace("\\data\\storage", local_root)
                for cand in (alt1, alt2, alt3, alt4):
                    if os.path.isfile(cand):
                        clean_path = cand
                        break
            if not os.path.isfile(clean_path):
                return ToolResult(
                    tool_name="analyze_image",
                    success=False,
                    result=None,
                    error=f"Image file not found: {clean_path}",
                )
            try:
                with open(clean_path, "rb") as f:
                    image_bytes = f.read()
            except Exception as e:
                return ToolResult(
                    tool_name="analyze_image",
                    success=False,
                    result=None,
                    error=f"Failed to read image file '{clean_path}': {e}",
                )
        else:
            return ToolResult(
                tool_name="analyze_image",
                success=False,
                result=None,
                error="Must provide either 'image_path' or 'image_base64'.",
            )

        if not image_bytes:
            return ToolResult(
                tool_name="analyze_image",
                success=False,
                result=None,
                error="Image content is empty.",
            )

        try:
            if task == "classify":
                classification = await asyncio.to_thread(
                    self._vision_provider.classify_image,
                    image_bytes=image_bytes,
                )
                msg = f"Image classification: {classification}"
                return ToolResult(
                    tool_name="analyze_image",
                    success=True,
                    result=AnalyzeImageResult(
                        msg,
                        raw_text=classification,
                        model=self._vision_provider._model,
                    ),
                )
            else:
                default_prompt = (
                    "Describe this image thoroughly. "
                    "If it shows refinery or industrial equipment, identify all components, labels, gauges, and conditions. "
                    "If it is a general, cartoon, meme, animal, person, or non-refinery image, describe what is depicted "
                    "in detail (characters, objects, actions, setting, colors, text) and note that it is non-industrial."
                )
                query_prompt = prompt if (isinstance(prompt, str) and prompt.strip()) else default_prompt

                vision_result: VisionResult = await asyncio.to_thread(
                    self._vision_provider.describe_image,
                    image_bytes=image_bytes,
                    prompt=query_prompt,
                )

                content = f"Image Analysis ({vision_result.model}):\n{vision_result.text}"
                return ToolResult(
                    tool_name="analyze_image",
                    success=True,
                    result=AnalyzeImageResult(
                        content,
                        raw_text=vision_result.text,
                        model=vision_result.model,
                        eval_count=vision_result.eval_count,
                    ),
                )

        except RuntimeError as e:
            logger.warning("Vision model communication error: %s", e)
            return ToolResult(
                tool_name="analyze_image",
                success=False,
                result=None,
                error=(
                    f"Vision model error: {str(e)}. "
                    "Ensure the vision model ('gemma3:4b') is installed via 'ollama pull gemma3:4b'."
                ),
            )
        except Exception as e:
            logger.error("AnalyzeImageTool unexpected error: %s", e, exc_info=True)
            return ToolResult(
                tool_name="analyze_image",
                success=False,
                result=None,
                error=f"Image analysis failed: {str(e)}",
            )
