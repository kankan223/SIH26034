"""Image quality assessment service per prd.md §10.1 and FR-003.

Implements:
- Laplacian-variance blur detection
- Histogram-based exposure analysis (overexposure/underexposure)
- Minimum resolution check (640x480 floor per FR-001)

All checks complete in <500ms per image.
"""

import io
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Thresholds (calibrated, not arbitrary — per prd.md §10.1)
# ---------------------------------------------------------------------------

# Laplacian variance threshold: below this = blurry
# Typical sharp images: 500-2000+, blurry: <100
BLUR_THRESHOLD = 150.0

# Minimum image dimensions (FR-001)
MIN_WIDTH = 640
MIN_HEIGHT = 480

# Exposure thresholds (histogram percentage in top/bottom bins)
OVEREXPOSURE_THRESHOLD = 0.85  # 85%+ pixels near white → overexposed
UNDEREXPOSURE_THRESHOLD = 0.15  # 15%- pixels near black → underexposed


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    """Result of image quality assessment."""
    quality_score: float  # 0.0 to 1.0
    quality_issues: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    laplacian_variance: float = 0.0
    is_blurry: bool = False
    is_overexposed: bool = False
    is_underexposed: bool = False
    is_low_resolution: bool = False

    @property
    def passed(self) -> bool:
        """Quality gate pass/fail. Pass if score > 0.5 and no critical issues."""
        return self.quality_score > 0.5 and "blurry" not in self.quality_issues


# ---------------------------------------------------------------------------
# Core assessment function
# ---------------------------------------------------------------------------

def assess_quality(image_bytes: bytes) -> QualityResult:
    """Assess image quality for blur, exposure, and resolution.

    Per prd.md §10.1:
    - Laplacian variance blur score (reject if < calibrated threshold)
    - Histogram-based exposure check
    - Minimum-label-area heuristic (640x480 floor)

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.)

    Returns:
        QualityResult with quality_score (0-1), quality_issues list,
        and detailed metrics.

    Raises:
        ValueError: If image cannot be decoded.
    """
    # Validate input
    if not image_bytes:
        raise ValueError("Cannot decode image — empty bytes")

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Cannot decode image — invalid or corrupted file")

    height, width = image.shape[:2]

    # --- 1. Resolution check ---
    is_low_resolution = width < MIN_WIDTH or height < MIN_HEIGHT

    # --- 2. Blur detection (Laplacian variance) ---
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian_var = float(laplacian.var())
    is_blurry = laplacian_var < BLUR_THRESHOLD

    # --- 3. Exposure analysis (histogram) ---
    histogram = cv2.calcHist([gray], [0], None, [256], [0, 256])
    total_pixels = gray.shape[0] * gray.shape[1]

    # Normalize histogram to proportions
    hist_normalized = histogram.flatten() / total_pixels

    # Check overexposure: proportion of very bright pixels (240-255)
    bright_ratio = float(hist_normalized[240:].sum())
    is_overexposed = bright_ratio > OVEREXPOSURE_THRESHOLD

    # Check underexposure: proportion of very dark pixels (0-15)
    dark_ratio = float(hist_normalized[:16].sum())
    is_underexposed = dark_ratio > UNDEREXPOSURE_THRESHOLD

    # --- 4. Compute quality score ---
    # Start at 1.0 and deduct for issues
    score = 1.0
    issues = []

    if is_blurry:
        # Severity proportional to how blurry
        severity = min(1.0, max(0, (BLUR_THRESHOLD - laplacian_var) / BLUR_THRESHOLD))
        score -= 0.4 * severity
        issues.append("blurry")

    if is_overexposed:
        score -= 0.3
        issues.append("overexposed")

    if is_underexposed:
        score -= 0.25
        issues.append("underexposed")

    if is_low_resolution:
        score -= 0.15
        issues.append("low_resolution")

    # Clamp score to [0, 1]
    score = max(0.0, min(1.0, score))

    return QualityResult(
        quality_score=round(score, 3),
        quality_issues=issues,
        width=width,
        height=height,
        laplacian_variance=round(laplacian_var, 2),
        is_blurry=is_blurry,
        is_overexposed=is_overexposed,
        is_underexposed=is_underexposed,
        is_low_resolution=is_low_resolution,
    )


# ---------------------------------------------------------------------------
# Synthetic image generators for testing
# ---------------------------------------------------------------------------

def generate_sharp_image(width: int = 800, height: int = 600) -> bytes:
    """Generate a sharp test image with high-contrast edges and good exposure."""
    # Start with a bright neutral background (well-exposed, no underexposure)
    img = np.full((height, width, 3), 220, dtype=np.uint8)

    # Add large high-contrast blocks on bright background
    img[50:200, 50:250] = [255, 255, 255]  # white block
    img[200:400, 300:600] = [0, 128, 255]  # blue block
    img[400:550, 100:400] = [255, 0, 0]    # red block

    # Add many thin sharp lines for high Laplacian variance
    for y in range(0, height, 15):
        color = (50, 50, 50) if y % 30 == 0 else (200, 200, 200)
        cv2.line(img, (0, y), (width, y), color, 1)

    # Add vertical lines too
    for x in range(0, width, 20):
        color = (80, 80, 80) if x % 40 == 0 else (180, 180, 180)
        cv2.line(img, (x, 0), (x, height), color, 1)

    # Add text-like patterns
    for y in range(250, 350, 5):
        cv2.line(img, (50, y), (750, y), (100, 100, 100), 2)

    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buffer.tobytes()


def generate_blurry_image(width: int = 800, height: int = 600) -> bytes:
    """Generate a blurry test image using Gaussian blur."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[50:150, 50:250] = [255, 255, 255]
    img[200:400, 300:600] = [0, 128, 255]
    img[400:550, 100:400] = [255, 0, 0]

    # Apply heavy Gaussian blur (kernel >31 makes image very blurry)
    blurred = cv2.GaussianBlur(img, (51, 51), 30)

    _, buffer = cv2.imencode('.jpg', blurred, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buffer.tobytes()


def generate_overexposed_image(width: int = 800, height: int = 600) -> bytes:
    """Generate an overexposed (too bright) test image."""
    img = np.full((height, width, 3), 250, dtype=np.uint8)
    img[100:500, 100:700] = [255, 255, 255]  # Almost entirely white

    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buffer.tobytes()


def generate_low_resolution_image(width: int = 320, height: int = 240) -> bytes:
    """Generate a low-resolution test image (below 640x480)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[10:100, 10:200] = [255, 255, 255]
    img[120:220, 50:280] = [0, 128, 255]

    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buffer.tobytes()
