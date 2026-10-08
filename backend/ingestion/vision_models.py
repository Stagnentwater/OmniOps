"""Data models for visual evidence extracted from images.

These models support the image ingestion pipeline (V15-IMG-001) and are
referenced by VisualEvidence fields on DocumentContent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """Spatial location of a detected entity within an image."""

    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    entity_type: str  # "asset", "component", "label", "line"


@dataclass(frozen=True)
class VisualEvidence:
    """Evidence extracted from a visual source (image, diagram, P&ID).

    Attached to DocumentContent.visual_evidence for provenance tracking.
    """

    image_uri: str
    source_type: str  # "photograph", "pid", "diagram", "screenshot", "scanned"
    extracted_text: str
    classification: str
    confidence: float
    bounding_boxes: tuple[BoundingBox, ...] = ()
    parent_page: int | None = None
