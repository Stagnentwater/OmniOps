"""Image parser: converts standalone image files to DocumentContent.

Orchestrates the image ingestion flow:
1. Classify the image (via VisionProvider)
2. Preprocess adaptively (via ImagePreprocessor)
3. Extract text description (via VisionProvider)
4. Package as DocumentContent with VisualEvidence

The original image is never modified and remains stored via StorageService.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ingestion.models import DocumentContent
from ingestion.vision_models import VisualEvidence
from generation.vision_provider import VisionProvider, VisionResult

logger = logging.getLogger(__name__)

# Supported standalone image extensions
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff"})


def is_image_file(filename: str) -> bool:
    """Check whether a filename has a supported image extension."""
    if "." not in filename:
        return False
    ext = "." + filename.rsplit(".", 1)[1].lower()
    return ext in IMAGE_EXTENSIONS


def parse_image(
    image_bytes: bytes,
    filename: str,
    vision_provider: VisionProvider,
    max_resolution: int = 2048,
    storage_uri: str = "",
) -> DocumentContent:
    """Parse a standalone image file into a DocumentContent.

    Args:
        image_bytes: Raw bytes of the image file.
        filename: Original filename (e.g., "pump_photo.jpg").
        vision_provider: The VisionProvider instance for model inference.
        max_resolution: Max dimension for preprocessing resize.
        storage_uri: URI where the original image is stored (for provenance).

    Returns:
        A DocumentContent containing the vision-extracted text and VisualEvidence.
    """
    t0 = time.time()

    # 1. Classify the image
    logger.info("[%s] Classifying image...", filename)
    classification = vision_provider.classify_image(image_bytes)
    t_classify = time.time() - t0
    logger.info(
        "[%s] Classification: %s (%.1fs)", filename, classification, t_classify,
    )

    # 2. Preprocess adaptively based on classification
    logger.info("[%s] Preprocessing (class=%s)...", filename, classification)
    from ingestion.image_preprocessor import preprocess_image
    preprocessed = preprocess_image(
        image_bytes, classification=classification, max_resolution=max_resolution,
    )
    t_preprocess = time.time() - t0 - t_classify
    logger.info("[%s] Preprocessing complete (%.1fs)", filename, t_preprocess)

    # 3. Build classification-specific prompt
    prompt = _build_prompt(classification)

    # 4. Send to vision model for description
    logger.info("[%s] Running vision inference...", filename)
    vision_result = vision_provider.describe_image(preprocessed, prompt=prompt)
    t_vision = time.time() - t0 - t_classify - t_preprocess
    logger.info(
        "[%s] Vision inference complete (%.1fs, %d tokens)",
        filename,
        t_vision,
        vision_result.eval_count,
    )

    # 5. Build the extracted text
    extracted_text = vision_result.text.strip()
    if not extracted_text:
        logger.warning("[%s] Vision model returned empty text.", filename)
        extracted_text = f"[Image: {filename} — no text extracted]"

    # 6. Create VisualEvidence
    evidence = VisualEvidence(
        image_uri=storage_uri,
        source_type=classification.lower(),
        extracted_text=extracted_text,
        classification=classification,
        confidence=0.8,  # Base confidence for vision extraction
    )

    # 7. Package as DocumentContent
    total_time = time.time() - t0
    logger.info("[%s] Image parsing complete (%.1fs total)", filename, total_time)

    return DocumentContent(
        filename=filename,
        text=extracted_text,
        pages=(extracted_text,),
        page_count=1,
        metadata={
            "source_type": "image",
            "image_classification": classification,
            "vision_model": vision_result.model,
            "vision_duration_ns": vision_result.total_duration_ns,
            "vision_eval_count": vision_result.eval_count,
            "original_image_uri": storage_uri,
            "parse_time_seconds": round(total_time, 2),
        },
        visual_evidence=(evidence,),
    )


def _build_prompt(classification: str) -> str:
    """Build a classification-specific vision prompt."""
    base = (
        "You are analyzing an industrial document image. "
        "Extract ALL information visible in the image.\n\n"
    )

    if classification == "PID":
        return base + (
            "This is a Piping & Instrumentation Diagram (P&ID).\n"
            "Identify and list:\n"
            "- All equipment (pumps, valves, vessels, heat exchangers, etc.)\n"
            "- Equipment tags and identifiers (e.g., P-301, V-200)\n"
            "- All instruments and their tag numbers\n"
            "- All piping connections and flow directions\n"
            "- Line numbers and specifications\n"
            "- Any notes, legends, or revision information\n"
            "- Process conditions (temperature, pressure, flow)\n"
            "Format the output as structured text with clear sections."
        )

    if classification == "SCANNED_DOCUMENT":
        return base + (
            "This is a scanned document. Perform OCR and extract:\n"
            "- All visible text, preserving layout where possible\n"
            "- Tables and their contents\n"
            "- Headers, footers, and page numbers\n"
            "- Any stamps, signatures, or annotations\n"
            "- Form fields and their values"
        )

    if classification == "SCREENSHOT":
        return base + (
            "This is a screenshot. Extract:\n"
            "- All visible text and labels\n"
            "- Data values, readings, or measurements shown\n"
            "- Any alarms, warnings, or status indicators\n"
            "- UI elements and their current state"
        )

    if classification == "DIAGRAM":
        return base + (
            "This is a technical diagram. Identify and describe:\n"
            "- All labeled components and their identifiers\n"
            "- Connections and relationships between components\n"
            "- Any measurements, dimensions, or specifications\n"
            "- Legend items and their meanings\n"
            "- Title block information"
        )

    # Default: PHOTOGRAPH
    return base + (
        "This is an industrial equipment photograph. Describe:\n"
        "- All visible equipment, components, and machinery\n"
        "- Manufacturer names, model numbers, and serial numbers\n"
        "- Any visible labels, tags, or nameplates\n"
        "- Condition of equipment (corrosion, damage, wear)\n"
        "- Connected piping, wiring, or instrumentation\n"
        "- Environmental context (indoor/outdoor, area type)"
    )
