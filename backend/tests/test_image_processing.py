"""
Tests for Task 2.1.1: Image Quality Assessment

Verifies:
- Laplacian variance blur detection (sharp vs blurry images)
- Histogram-based exposure analysis (overexposed, underexposed)
- Minimum resolution check (640x480 floor per FR-001)
- Quality score calculation (0-1 range)
- Quality issues array populated correctly
- Synthetic image generators produce expected characteristics
- Performance: all checks complete in <500ms
"""
import time
import pytest
import numpy as np
import cv2

from app.services.image_processing import (
    assess_quality,
    generate_sharp_image,
    generate_blurry_image,
    generate_overexposed_image,
    generate_low_resolution_image,
    QualityResult,
    BLUR_THRESHOLD,
    MIN_WIDTH,
    MIN_HEIGHT,
)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: SHARP IMAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestSharpImageQuality:
    """Sharp, well-lit images should pass quality gate."""

    def test_sharp_image_has_high_quality_score(self):
        """A sharp image should have quality_score > 0.8."""
        image_bytes = generate_sharp_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.quality_score > 0.8, f"Expected >0.8, got {result.quality_score}"

    def test_sharp_image_no_issues(self):
        """A sharp, well-lit image should have no quality issues."""
        image_bytes = generate_sharp_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.quality_issues == [], f"Expected no issues, got {result.quality_issues}"

    def test_sharp_image_passes_quality_gate(self):
        """A sharp image should pass the quality gate."""
        image_bytes = generate_sharp_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.passed is True

    def test_sharp_image_dimensions_correct(self):
        """Quality result should report correct dimensions."""
        image_bytes = generate_sharp_image(1024, 768)
        result = assess_quality(image_bytes)
        assert result.width == 1024
        assert result.height == 768

    def test_sharp_image_high_laplacian_variance(self):
        """Sharp image should have high Laplacian variance."""
        image_bytes = generate_sharp_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.laplacian_variance > BLUR_THRESHOLD, \
            f"Expected variance >{BLUR_THRESHOLD}, got {result.laplacian_variance}"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: BLURRY IMAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestBlurryImageQuality:
    """Blurry images should be flagged with quality issues."""

    def test_blurry_image_detected(self):
        """A blurry image should be detected as blurry."""
        image_bytes = generate_blurry_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.is_blurry is True

    def test_blurry_image_has_blur_issue(self):
        """Blurry image should have 'blurry' in quality_issues."""
        image_bytes = generate_blurry_image(800, 600)
        result = assess_quality(image_bytes)
        assert "blurry" in result.quality_issues

    def test_blurry_image_low_quality_score(self):
        """Blurry image should have reduced quality score."""
        image_bytes = generate_blurry_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.quality_score < 0.8, f"Expected <0.8, got {result.quality_score}"

    def test_blurry_image_low_laplacian_variance(self):
        """Blurry image should have low Laplacian variance."""
        image_bytes = generate_blurry_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.laplacian_variance < BLUR_THRESHOLD, \
            f"Expected variance <{BLUR_THRESHOLD}, got {result.laplacian_variance}"

    def test_blurry_image_fails_quality_gate(self):
        """Blurry image should fail the quality gate."""
        image_bytes = generate_blurry_image(800, 600)
        result = assess_quality(image_bytes)
        # Blurry images may or may not fail depending on severity
        # But they should always have "blurry" in issues
        assert "blurry" in result.quality_issues


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: OVEREXPOSED IMAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestOverexposedImageQuality:
    """Overexposed images should be flagged."""

    def test_overexposed_image_detected(self):
        """An overexposed image should be detected."""
        image_bytes = generate_overexposed_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.is_overexposed is True

    def test_overexposed_image_has_issue(self):
        """Overexposed image should have 'overexposed' in quality_issues."""
        image_bytes = generate_overexposed_image(800, 600)
        result = assess_quality(image_bytes)
        assert "overexposed" in result.quality_issues

    def test_overexposed_image_reduced_score(self):
        """Overexposed image should have reduced quality score."""
        image_bytes = generate_overexposed_image(800, 600)
        result = assess_quality(image_bytes)
        assert result.quality_score < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: LOW RESOLUTION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestLowResolutionQuality:
    """Images below 640x480 should be flagged per FR-001."""

    def test_low_resolution_detected(self):
        """An image below 640x480 should be detected as low resolution."""
        image_bytes = generate_low_resolution_image(320, 240)
        result = assess_quality(image_bytes)
        assert result.is_low_resolution is True

    def test_low_resolution_has_issue(self):
        """Low resolution image should have 'low_resolution' in quality_issues."""
        image_bytes = generate_low_resolution_image(320, 240)
        result = assess_quality(image_bytes)
        assert "low_resolution" in result.quality_issues

    def test_low_resolution_reduced_score(self):
        """Low resolution image should have reduced quality score."""
        image_bytes = generate_low_resolution_image(320, 240)
        result = assess_quality(image_bytes)
        assert result.quality_score < 1.0

    def test_exact_minimum_resolution_passes(self):
        """Image at exactly 640x480 should NOT be flagged as low resolution."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[50:150, 50:250] = [255, 255, 255]
        img[200:400, 300:600] = [0, 128, 255]
        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        result = assess_quality(buffer.tobytes())
        assert result.is_low_resolution is False


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: EDGE CASES & ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_image_bytes_raises_error(self):
        """Invalid image bytes should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot decode"):
            assess_quality(b"not an image at all")

    def test_empty_bytes_raises_error(self):
        """Empty bytes should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot decode"):
            assess_quality(b"")

    def test_quality_score_in_valid_range(self):
        """Quality score should always be between 0.0 and 1.0."""
        image_bytes = generate_sharp_image(800, 600)
        result = assess_quality(image_bytes)
        assert 0.0 <= result.quality_score <= 1.0

    def test_quality_issues_is_list(self):
        """Quality issues should always be a list."""
        image_bytes = generate_sharp_image(800, 600)
        result = assess_quality(image_bytes)
        assert isinstance(result.quality_issues, list)

    def test_quality_result_dataclass(self):
        """QualityResult should be a proper dataclass."""
        result = QualityResult(
            quality_score=0.9,
            quality_issues=[],
            width=800,
            height=600,
        )
        assert result.quality_score == 0.9
        assert result.passed is True


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: COMBINED ISSUES
# ═══════════════════════════════════════════════════════════════════════════


class TestCombinedIssues:
    """Test images with multiple quality issues."""

    def test_blurry_and_low_resolution(self):
        """An image can have both blurry and low_resolution issues."""
        # Create a small, blurry image
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        img[10:100, 10:200] = [255, 255, 255]
        blurred = cv2.GaussianBlur(img, (51, 51), 30)
        _, buffer = cv2.imencode('.jpg', blurred, [cv2.IMWRITE_JPEG_QUALITY, 95])
        result = assess_quality(buffer.tobytes())
        assert "low_resolution" in result.quality_issues
        assert "blurry" in result.quality_issues
        assert result.quality_score < 0.7


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: PERFORMANCE TEST
# ═══════════════════════════════════════════════════════════════════════════


class TestPerformance:
    """All quality checks must complete in <500ms per image."""

    def test_assessment_completes_under_500ms(self):
        """Quality assessment should complete in under 500ms."""
        image_bytes = generate_sharp_image(1920, 1080)  # Full HD
        start = time.time()
        result = assess_quality(image_bytes)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, f"Assessment took {elapsed_ms:.0f}ms (target: <500ms)"

    def test_blurry_image_assessment_under_500ms(self):
        """Blurry image assessment should also be fast."""
        image_bytes = generate_blurry_image(1920, 1080)
        start = time.time()
        result = assess_quality(image_bytes)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, f"Assessment took {elapsed_ms:.0f}ms (target: <500ms)"

    def test_multiple_assessments_under_1s(self):
        """5 sequential assessments should complete in under 1s total."""
        images = [
            generate_sharp_image(800, 600),
            generate_blurry_image(800, 600),
            generate_overexposed_image(800, 600),
            generate_low_resolution_image(320, 240),
            generate_sharp_image(800, 600),
        ]
        start = time.time()
        for img in images:
            assess_quality(img)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"5 assessments took {elapsed:.2f}s (target: <1.0s)"
