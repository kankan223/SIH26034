"""Unit tests for font_analysis.py — font size estimation service.

Per prd.md §15: text-line height as fraction of package height.
No absolute mm values — only relative fractions. UNABLE_TO_VERIFY when
confidence below floor.
"""

import pytest

from app.services.font_analysis import (
    FontSizeResult,
    estimate_font_size,
    CONFIDENCE_FLOOR,
    RELATIVE_SIZE_THRESHOLDS,
)


class TestFontSizeResult:
    """Tests for FontSizeResult dataclass."""

    def test_font_size_result_default_values(self):
        """FontSizeResult should be constructable with all fields."""
        result = FontSizeResult(
            relative_size=0.05,
            measurement_confidence=0.85,
            text_region_type="legible",
            is_unable_to_verify=False,
            notes="Test note",
        )
        assert result.relative_size == 0.05
        assert result.measurement_confidence == 0.85
        assert result.text_region_type == "legible"
        assert result.is_unable_to_verify is False
        assert result.notes == "Test note"

    def test_font_size_result_optional_relative_size(self):
        """relative_size can be None when unable to verify."""
        result = FontSizeResult(
            relative_size=None,
            measurement_confidence=0.3,
            text_region_type="illegible",
            is_unable_to_verify=True,
            notes="Unable to verify",
        )
        assert result.relative_size is None
        assert result.is_unable_to_verify is True

    def test_font_size_result_equality(self):
        """FontSizeResult instances with same values should be equal."""
        r1 = FontSizeResult(
            relative_size=0.04, measurement_confidence=0.8,
            text_region_type="legible", is_unable_to_verify=False,
            notes="ok",
        )
        r2 = FontSizeResult(
            relative_size=0.04, measurement_confidence=0.8,
            text_region_type="legible", is_unable_to_verify=False,
            notes="ok",
        )
        assert r1 == r2


class TestEstimateFontSize:
    """Tests for estimate_font_size() function."""

    def test_clear_text_region_high_confidence(self):
        """Clear text region → high confidence, relative size returned."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.measurement_confidence > CONFIDENCE_FLOOR
        assert result.measurement_confidence > 0.7
        assert result.text_region_type == "legible"
        assert result.is_unable_to_verify is False
        assert result.relative_size is not None
        # text_line_height=40, package_height=450, ratio=0.0889
        assert 0.08 < result.relative_size < 0.09
        assert "unable to verify" not in result.notes.lower()

    def test_degraded_text_region_unable_to_verify(self):
        """Degraded text region → UNABLE_TO_VERIFY, no relative size."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 110, "y2": 204}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.measurement_confidence < CONFIDENCE_FLOOR
        assert result.is_unable_to_verify is True
        assert result.relative_size is None
        assert "unable to verify" in result.notes.lower()

    def test_font_analysis_completes_quickly(self):
        """Font analysis should complete in <10ms (prd.md §10.2)."""
        import time

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        start = time.time()
        for _ in range(100):
            estimate_font_size(ocr_bbox, package_bbox)
        elapsed = time.time() - start

        # 100 calls in <1s → each call <10ms
        assert elapsed < 1.0, f"100 calls took {elapsed:.3f}s, target <1s"

    def test_no_fabricated_mm_values(self):
        """Result should NOT contain any mm values — only relative fractions."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        # No mm values in notes
        assert "mm" not in result.notes.lower()
        assert "cm" not in result.notes.lower()
        # Only relative fraction in notes
        assert "%" in result.notes  # relative percentage

    def test_text_line_height_zero_returns_unable(self):
        """Zero-height OCR bbox → UNABLE_TO_VERIFY."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200}  # height=0
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.is_unable_to_verify is True
        assert result.measurement_confidence == 0.0
        assert result.relative_size is None
        assert "invalid" in result.notes.lower()

    def test_package_height_zero_returns_unable(self):
        """Zero-height package bbox → UNABLE_TO_VERIFY."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150}  # height=0

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.is_unable_to_verify is True
        assert result.measurement_confidence == 0.0
        assert result.relative_size is None

    def test_negative_bbox_dimensions_return_unable(self):
        """Negative height bbox → UNABLE_TO_VERIFY."""
        ocr_bbox = {"x1": 300, "y1": 240, "x2": 100, "y2": 200}  # inverted
        package_bbox = {"x1": 500, "y1": 600, "x2": 50, "y2": 150}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.is_unable_to_verify is True
        assert result.measurement_confidence == 0.0

    def test_text_larger_than_package_returns_unable(self):
        """Text line taller than package → UNABLE_TO_VERIFY (invalid ratio)."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 800}  # height=600
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}  # height=450

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.is_unable_to_verify is True
        assert result.measurement_confidence == 0.0
        assert "out of valid range" in result.notes.lower()

    def test_text_region_type_legible_threshold(self):
        """Text at legible threshold → legible region type."""
        # text height = 3% of package height → legible threshold
        package_height = 500
        text_height = int(package_height * RELATIVE_SIZE_THRESHOLDS["legible"])  # 15px

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + text_height}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150 + package_height}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.text_region_type == "legible"
        assert result.measurement_confidence > CONFIDENCE_FLOOR

    def test_text_region_type_marginal_threshold(self):
        """Text at marginal threshold → marginal region type."""
        package_height = 500
        text_height = int(package_height * RELATIVE_SIZE_THRESHOLDS["marginal"])  # 7.5 → 7

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + text_height}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150 + package_height}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.text_region_type in ("marginal", "degraded")
        # Below legible threshold but above illegible

    def test_text_region_type_illegible_threshold(self):
        """Text below illegible threshold → illegible region type."""
        package_height = 500
        text_height = int(package_height * RELATIVE_SIZE_THRESHOLDS["illegible"]) - 1  # 3px

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + text_height}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150 + package_height}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.text_region_type == "illegible"
        assert result.is_unable_to_verify is True

    def test_confidence_below_floor_marks_unable_to_verify(self):
        """Confidence below floor → is_unable_to_verify=True."""
        # Use a very small text that falls below confidence floor
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + 2}  # 2px text
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.is_unable_to_verify is True
        assert result.measurement_confidence < CONFIDENCE_FLOOR

    def test_confidence_above_floor_not_unable(self):
        """Confidence above floor → is_unable_to_verify=False."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + 40}  # 40px text
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.is_unable_to_verify is False
        assert result.measurement_confidence >= CONFIDENCE_FLOOR

    def test_relative_size_proportional_to_text_and_package(self):
        """Scaling both text and package by same factor → same relative size."""
        base_ocr = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        base_pkg = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result1 = estimate_font_size(base_ocr, base_pkg)

        # Scale BOTH text and package by 2x (maintain ratio)
        # base: text_height=40, package_height=450, ratio=40/450≈0.089
        # 2x:  text_height=80, package_height=900, ratio=80/900≈0.089
        double_ocr = {"x1": 100, "y1": 200, "x2": 300, "y2": 280}    # 80px text (2x)
        double_pkg = {"x1": 50, "y1": 150, "x2": 500, "y2": 1050}   # 900px pkg (2x)

        result2 = estimate_font_size(double_ocr, double_pkg)

        # Ratios should be approximately equal (40/450 = 80/900)
        assert abs(result1.relative_size - result2.relative_size) < 0.005

    def test_marginal_region_includes_confidence_note(self):
        """Marginal region should have appropriate note."""
        package_height = 500
        text_height = max(1, int(package_height * 0.02))  # 10px → 2% → marginal

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + text_height}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150 + package_height}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.text_region_type in ("marginal", "degraded")
        assert "uncertain" in result.notes.lower() or "approximately" in result.notes.lower()

    def test_illegible_region_note(self):
        """Illegible region should have 'too small or degraded' note."""
        package_height = 500
        text_height = max(1, int(package_height * 0.005))  # 2.5px → illegible

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + text_height}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150 + package_height}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.text_region_type == "illegible"
        assert result.is_unable_to_verify is True
        assert "degraded" in result.notes.lower() or "unable" in result.notes.lower()

    def test_very_large_text_still_legible(self):
        """Text that's a large fraction of package → still legible."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 400}  # 200px text
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}  # 450px package

        result = estimate_font_size(ocr_bbox, package_bbox)

        # ratio = 200/450 ≈ 0.444 → well above legible threshold
        assert result.text_region_type == "legible"
        assert result.is_unable_to_verify is False
        assert result.measurement_confidence > 0.7

    def test_boundary_at_confidence_floor(self):
        """Text exactly at confidence floor boundary."""
        # Find a text height that produces confidence near the floor
        # degraded: 0.5 confidence at illegible threshold (0.8% of package)
        package_height = 500
        text_height = max(1, int(package_height * 0.008))  # 4px

        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 200 + text_height}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 150 + package_height}

        result = estimate_font_size(ocr_bbox, package_bbox)

        # At illegible threshold, confidence = 0.5, floor = 0.5
        # 0.5 < 0.5 is False, so not unable — borderline case
        assert result.measurement_confidence <= 0.5 + 0.01  # at or near floor

    def test_estimate_font_size_returns_dataclass(self):
        """estimate_font_size should return FontSizeResult instance."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert isinstance(result, FontSizeResult)

    def test_multiple_calls_deterministic(self):
        """Same inputs should produce same outputs (deterministic)."""
        ocr_bbox = {"x1": 100, "y1": 200, "x2": 300, "y2": 240}
        package_bbox = {"x1": 50, "y1": 150, "x2": 500, "y2": 600}

        result1 = estimate_font_size(ocr_bbox, package_bbox)
        result2 = estimate_font_size(ocr_bbox, package_bbox)

        assert result1 == result2


class TestConfidenceThresholds:
    """Tests for confidence threshold constants."""

    def test_confidence_floor_is_positive(self):
        """CONFIDENCE_FLOOR should be a positive number between 0 and 1."""
        assert 0 < CONFIDENCE_FLOOR < 1

    def test_relative_size_thresholds_ordered(self):
        """Thresholds should be ordered: legible > marginal > illegible."""
        assert (
            RELATIVE_SIZE_THRESHOLDS["legible"]
            > RELATIVE_SIZE_THRESHOLDS["marginal"]
            > RELATIVE_SIZE_THRESHOLDS["illegible"]
        )

    def test_all_thresholds_positive(self):
        """All threshold values should be positive."""
        for name, value in RELATIVE_SIZE_THRESHOLDS.items():
            assert value > 0, f"{name} threshold should be positive"


class TestIntegration:
    """Integration tests for font_analysis with OCR-like data."""

    def test_ocr_bbox_from_paddleocr_format(self):
        """Simulate OCR bbox in PaddleOCR format (4-point polygon)."""
        # PaddleOCR returns [x1, y1, x2, y2] as a simplified bbox
        # Here we simulate a text line bbox
        ocr_bbox = {"x1": 120, "y1": 180, "x2": 350, "y2": 215}
        package_bbox = {"x1": 50, "y1": 100, "x2": 550, "y2": 700}

        result = estimate_font_size(ocr_bbox, package_bbox)

        assert result.measurement_confidence > 0
        assert result.text_region_type in (
            "legible", "marginal", "degraded", "illegible"
        )

    def test_small_label_large_text(self):
        """Small package with large text → high relative size."""
        ocr_bbox = {"x1": 0, "y1": 100, "x2": 200, "y2": 170}  # 70px text
        package_bbox = {"x1": 0, "y1": 0, "x2": 200, "y2": 200}  # 200px package

        result = estimate_font_size(ocr_bbox, package_bbox)

        # ratio = 70/200 = 0.35 → legible
        assert result.text_region_type == "legible"
        assert not result.is_unable_to_verify

    def test_large_label_small_text(self):
        """Large package with tiny text → low confidence."""
        ocr_bbox = {"x1": 0, "y1": 950, "x2": 1000, "y2": 955}  # 5px text
        package_bbox = {"x1": 0, "y1": 0, "x2": 1000, "y2": 1000}  # 1000px package

        result = estimate_font_size(ocr_bbox, package_bbox)

        # ratio = 5/1000 = 0.005 → illegible
        assert result.is_unable_to_verify
        assert result.relative_size is None
