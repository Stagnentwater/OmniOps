"""Automatic model routing for multi-model architecture.

Routes tasks to the appropriate model based on file type, task type,
and image classification. The user never selects a model manually —
this router makes the decision automatically.

The selected model is logged for debugging but hidden from end users.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# File extensions that trigger the vision pipeline
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff"})

# File extensions handled by standard document parsers
_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".csv", ".xlsx", ".xls"})


class ModelRouter:
    """Determines the correct model and pipeline for a given task.

    Examines the input (file type, task intent, etc.) and routes to
    the appropriate processing pipeline and Ollama model.
    """

    def __init__(
        self,
        reasoning_model: str = "llama3.2",
        vision_model: str = "gemma3:4b",
    ) -> None:
        self._reasoning_model = reasoning_model
        self._vision_model = vision_model

    def route_file(self, filename: str) -> dict[str, str]:
        """Determine the pipeline and model for a file upload.

        Args:
            filename: The uploaded file's name.

        Returns:
            A dict with keys 'pipeline' and 'model'.
        """
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()

        if ext in _IMAGE_EXTENSIONS:
            result = {
                "pipeline": "image",
                "model": self._vision_model,
                "parser": "image_parser",
            }
        elif ext in _DOCUMENT_EXTENSIONS:
            result = {
                "pipeline": "document",
                "model": self._reasoning_model,
                "parser": self._get_document_parser(ext),
            }
        else:
            result = {
                "pipeline": "unknown",
                "model": self._reasoning_model,
                "parser": "none",
            }

        logger.info(
            "ModelRouter: file=%s → pipeline=%s, model=%s",
            filename,
            result["pipeline"],
            result["model"],
        )
        return result

    def route_query(self, has_image: bool = False) -> dict[str, str]:
        """Determine the model for a chat query.

        Args:
            has_image: Whether the query includes an image attachment.

        Returns:
            A dict with keys 'pipeline' and 'model'.
        """
        if has_image:
            result = {"pipeline": "vision_query", "model": self._vision_model}
        else:
            result = {"pipeline": "text_query", "model": self._reasoning_model}

        logger.info(
            "ModelRouter: query → pipeline=%s, model=%s",
            result["pipeline"],
            result["model"],
        )
        return result

    def select_model(self, task_type: str) -> str:
        """Return the model name for a given task type.

        Args:
            task_type: One of "image_classify", "image_vision", "pid_verify",
                "text_query", "reasoning", "generation".

        Returns:
            The Ollama model name string.
        """
        if task_type in ("image_classify", "image_vision", "pid_verify"):
            model = self._vision_model
        else:
            model = self._reasoning_model

        logger.debug("ModelRouter: task=%s → model=%s", task_type, model)
        return model

    @staticmethod
    def _get_document_parser(ext: str) -> str:
        """Map file extension to parser name."""
        mapping = {
            ".pdf": "pdf_parser",
            ".docx": "docx_parser",
            ".csv": "csv_parser",
            ".xlsx": "excel_parser",
            ".xls": "excel_parser",
        }
        return mapping.get(ext, "unknown")
