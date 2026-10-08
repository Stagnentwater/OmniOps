"""Adaptive image preprocessing for the vision pipeline.

Applies classification-based preprocessing to images before
sending them to the vision model. The original image is never
modified — preprocessing produces a temporary copy.

OpenCV is imported lazily so the module can be loaded even when
opencv-python-headless is not installed (for tests, etc.).
"""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Image format MIME type to PIL-compatible format mapping
_FORMAT_MAP: dict[str, str] = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".bmp": "BMP",
}


def preprocess_image(
    image_bytes: bytes,
    classification: str = "PHOTOGRAPH",
    max_resolution: int = 2048,
) -> bytes:
    """Apply adaptive preprocessing to raw image bytes.

    Args:
        image_bytes: Raw file bytes of the image.
        classification: Image class from the classifier
            (PID, PHOTOGRAPH, DIAGRAM, SCREENSHOT, SCANNED_DOCUMENT).
        max_resolution: Maximum dimension in pixels for the longest side.

    Returns:
        Preprocessed image as JPEG bytes.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.warning(
            "opencv-python-headless not installed. Returning original image."
        )
        return image_bytes

    # Decode raw bytes to OpenCV image
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        logger.error("Failed to decode image bytes. Returning original.")
        return image_bytes

    # 1. Resize to max resolution (preserve aspect ratio)
    img = _resize_to_max(img, max_resolution)

    # 2. Apply classification-specific preprocessing
    if classification == "SCANNED_DOCUMENT":
        img = _preprocess_scanned(img)
    elif classification == "PID":
        img = _preprocess_pid(img)
    elif classification == "PHOTOGRAPH":
        img = _preprocess_photograph(img)
    elif classification == "DIAGRAM":
        img = _preprocess_diagram(img)
    # SCREENSHOT: no preprocessing needed — already clean

    # Encode back to JPEG bytes
    success, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        logger.error("Failed to encode preprocessed image. Returning original.")
        return image_bytes

    return encoded.tobytes()


def _resize_to_max(img: Any, max_dim: int) -> Any:
    """Resize image so longest side is at most max_dim pixels."""
    import cv2

    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img

    scale = max_dim / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _preprocess_photograph(img: Any) -> Any:
    """Light CLAHE contrast enhancement for photographs."""
    import cv2

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


def _preprocess_scanned(img: Any) -> Any:
    """Deskew + binarize + denoise for scanned documents."""
    import cv2
    import numpy as np

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Deskew
    gray = _deskew(gray)

    # Denoise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Adaptive threshold (binarize)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Convert back to BGR for consistent pipeline output
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _preprocess_pid(img: Any) -> Any:
    """CLAHE + deskew for P&ID diagrams (no binarization to preserve color)."""
    import cv2

    # Deskew on grayscale, apply to color
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    angle = _detect_skew_angle(gray)
    if abs(angle) > 0.5:
        img = _rotate_image(img, angle)

    # CLAHE on luminance channel
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


def _preprocess_diagram(img: Any) -> Any:
    """CLAHE contrast for generic diagrams."""
    return _preprocess_photograph(img)  # Same treatment


def _deskew(gray: Any) -> Any:
    """Detect and correct skew on a grayscale image."""
    import cv2

    angle = _detect_skew_angle(gray)
    if abs(angle) > 0.5:
        return _rotate_image(gray, angle)
    return gray


def _detect_skew_angle(gray: Any) -> float:
    """Detect dominant skew angle using Hough Line Transform."""
    import cv2
    import numpy as np

    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100,
        minLineLength=100, maxLineGap=10,
    )

    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Only consider near-horizontal lines (likely text baselines)
        if abs(angle) < 45:
            angles.append(angle)

    if not angles:
        return 0.0

    return float(np.median(angles))


def _rotate_image(img: Any, angle: float) -> Any:
    """Rotate image by the given angle (in degrees) around its center."""
    import cv2

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
