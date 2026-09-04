"""Font size estimation using relative-proxy method.

Per prd.md §15: text-line height as a fraction of package/label bbox height.
No physical reference = relative fraction only, never fabricate absolute mm values.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FontSizeResult:
    """Result of font size estimation.

    Attributes:
        relative_size: The text line height as a fraction of the package height.
            E.g., 0.05 means the text is 5% of the package height.
        measurement_confidence: Confidence in the measurement (0.0 to 1.0).
            Low confidence → UNABLE_TO_VERIFY state.
        text_region_type: Classification of the text region
            ('legible', 'degraded', 'marginal', 'illegible').
        is_unable_to_verify: True if confidence below floor — never fabricate.
        notes: Human-readable note for UI/report display.
    """
    relative_size: Optional[float]  # fraction of package height, None if unable
    measurement_confidence: float  # 0.0 to 1.0
    text_region_type: str  # 'legible' | 'degraded' | 'marginal' | 'illegible'
    is_unable_to_verify: bool
    notes: str


# Confidence floor per prd.md §15.7 — below this, we mark UNABLE_TO_VERIFY
CONFIDENCE_FLOOR = 0.5

# Relative size thresholds for text region classification
# These are heuristic thresholds based on typical label font sizes
RELATIVE_SIZE_THRESHOLDS = {
    "legible": 0.03,   # text is at least 3% of package height
    "marginal": 0.015,  # text is at least 1.5% of package height
    "illegible": 0.008,  # below this, text is too small to estimate reliably
}


def estimate_font_size(
    ocr_bbox: dict,
    package_bbox: dict,
) -> FontSizeResult:
    """Estimate font size using the relative-proxy method.

    Args:
        ocr_bbox: Dict with keys 'x1', 'y1', 'x2', 'y2' (top-left and bottom-right
            corners of the text line bounding box).
        package_bbox: Dict with keys 'x1', 'y1', 'x2', 'y2' (bounding box of the
            package/label region).

    Returns:
        FontSizeResult with relative size fraction and confidence score.
    """
    # Extract coordinates
    ocr_x1, ocr_y1, ocr_x2, ocr_y2 = (
        ocr_bbox["x1"], ocr_bbox["y1"], ocr_bbox["x2"], ocr_bbox["y2"]
    )
    pkg_x1, pkg_y1, pkg_x2, pkg_y2 = (
        package_bbox["x1"], package_bbox["y1"], package_bbox["x2"], package_bbox["y2"]
    )

    # Calculate text line height (in pixels)
    text_line_height = ocr_y2 - ocr_y1
    package_height = pkg_y2 - pkg_y1

    # Guard against zero or negative dimensions
    if text_line_height <= 0 or package_height <= 0:
        return FontSizeResult(
            relative_size=None,
            measurement_confidence=0.0,
            text_region_type="illegible",
            is_unable_to_verify=True,
            notes="Invalid bounding box dimensions",
        )

    # Calculate relative size: text_line_height / package_height
    relative_size = text_line_height / package_height

    # Guard against unreasonable ratios (text larger than package?)
    if relative_size > 1.0 or relative_size <= 0:
        return FontSizeResult(
            relative_size=None,
            measurement_confidence=0.0,
            text_region_type="illegible",
            is_unable_to_verify=True,
            notes="Text-to-package ratio out of valid range",
        )

    # Determine text region type based on relative size
    if relative_size >= RELATIVE_SIZE_THRESHOLDS["legible"]:
        text_region_type = "legible"
        base_confidence = 0.9
    elif relative_size >= RELATIVE_SIZE_THRESHOLDS["marginal"]:
        text_region_type = "marginal"
        base_confidence = 0.65
    elif relative_size >= RELATIVE_SIZE_THRESHOLDS["illegible"]:
        text_region_type = "degraded"
        base_confidence = 0.45
    else:
        text_region_type = "illegible"
        base_confidence = 0.2

    # Adjust confidence based on text region type
    # Clear/legible text → high confidence
    # Degraded text → lower confidence
    measurement_confidence = base_confidence

    # Below confidence floor → UNABLE_TO_VERIFY, never fabricate
    is_unable_to_verify = measurement_confidence < CONFIDENCE_FLOOR

    # Build notes for UI/report display
    if is_unable_to_verify:
        notes = "Unable to verify precisely — text too small or degraded"
    elif text_region_type == "legible":
        notes = f"Font estimated at ~{relative_size*100:.1f}% of label height (relative proxy)"
    elif text_region_type == "marginal":
        notes = f"Font approximately {relative_size*100:.1f}% of label height (low certainty)"
    else:
        notes = "Text region too degraded for reliable estimation"

    return FontSizeResult(
        relative_size=relative_size if not is_unable_to_verify else None,
        measurement_confidence=measurement_confidence,
        text_region_type=text_region_type,
        is_unable_to_verify=is_unable_to_verify,
        notes=notes,
    )
