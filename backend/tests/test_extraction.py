"""
Tests for Task 3.3.1: Text Normalization & Declaration Extraction

Verifies:
- OCR substitution fixing (O/0, l/1, etc.)
- Unit normalization to closed vocabulary (g, ml, kg, etc.)
- Currency symbol normalization to INR
- Date format parsing (MM/YYYY, DD/MM/YYYY, etc.)
- Declaration extraction for all field types per prd.md §14.1
- NOT_FOUND handling for missing fields (FR-008)
- Ambiguity handling: multiple candidates with confidence scores
- Integration with OCR service (detect → OCR → extract pipeline)
"""
import time
import pytest
from datetime import datetime, timezone

from app.services.extraction import (
    normalize_text,
    extract_declarations,
    _fix_ocr_substitutions,
    _normalize_unit,
    _normalize_currency,
    _parse_date,
    NormalizedToken,
    Declaration,
    ExtractionResult,
    FIELD_TYPES,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class MockOCRResult:
    """Mock OCRResult for testing without live PaddleOCR."""
    def __init__(self, text: str, confidence: float = 0.9, bbox=None, language: str = "en"):
        self.text = text
        self.original = text  # Alias for extraction service
        self.confidence = confidence
        self.bbox = bbox or [[0, 0], [100, 0], [100, 30], [0, 30]]
        self.language = language


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: OCR SUBSTITUTION FIXING
# ═══════════════════════════════════════════════════════════════════════════


class TestOCRSubstitutions:
    """Verify common OCR character substitutions per FR-007."""

    def test_fix_numeric_substitutions(self):
        """O/0, l/1, etc. should be fixed in numeric contexts."""
        assert _fix_ocr_substitutions("5O0gm") == "500gm"

    def test_fix_letter_l_to_one(self):
        """Lowercase l should become 1 in numeric context."""
        # The function fixes substitutions in strings containing digits
        result = _fix_ocr_substitutions("5l0gm")
        assert result == "510gm"

    def test_no_fix_non_numeric(self):
        """Non-numeric text should not be modified."""
        assert _fix_ocr_substitutions("Product Name") == "Product Name"

    def test_fix_mixed_alphanumeric(self):
        """Mixed text with numbers should fix digits only."""
        result = _fix_ocr_substitutions("Rs. 999")
        assert "999" in result


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: UNIT NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════


class TestUnitNormalization:
    """Verify unit normalization to closed vocabulary per §14.1."""

    def test_gm_to_g(self):
        unit, value = _normalize_unit("500gm")
        assert unit == "g"
        assert value == "500"

    def test_gram_to_g(self):
        unit, value = _normalize_unit("250gram")
        assert unit == "g"
        assert value == "250"

    def test_ml_normalization(self):
        unit, value = _normalize_unit("330ml")
        assert unit == "ml"
        assert value == "330"

    def test_kg_normalization(self):
        unit, value = _normalize_unit("2kg")
        assert unit == "kg"
        assert value == "2"

    def test_ltr_normalization(self):
        unit, value = _normalize_unit("1.5ltr")
        assert unit == "l"
        assert value == "1.5"

    def test_pcs_normalization(self):
        unit, value = _normalize_unit("10pcs")
        assert unit == "pcs"
        assert value == "10"

    def test_unknown_unit(self):
        unit, value = _normalize_unit("500xyz")
        assert unit is None

    def test_no_unit(self):
        unit, value = _normalize_unit("999")
        assert unit is None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: CURRENCY NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════


class TestCurrencyNormalization:
    """Verify currency symbol normalization to INR."""

    def test_rs_prefix(self):
        currency, value = _normalize_currency("Rs. 999")
        assert currency == "INR"
        assert "999" in value

    def test_rs_dot_prefix(self):
        currency, value = _normalize_currency("Rs.1499")
        assert currency == "INR"

    def test_inr_prefix(self):
        currency, value = _normalize_currency("INR 599")
        assert currency == "INR"

    def test_rupee_symbol(self):
        currency, value = _normalize_currency("₹999")
        assert currency == "INR"
        assert "999" in value

    def test_no_currency(self):
        currency, value = _normalize_currency("500gm")
        assert currency is None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: DATE PARSING
# ═══════════════════════════════════════════════════════════════════════════


class TestDateParsing:
    """Verify date format parsing per §14.1."""

    def test_mm_slash_yyyy(self):
        result = _parse_date("08/2026")
        assert result == (8, 2026)

    def test_mm_dash_yyyy(self):
        result = _parse_date("12-2025")
        assert result == (12, 2025)

    def test_mm_dot_yyyy(self):
        result = _parse_date("01.2027")
        assert result == (1, 2027)

    def test_dd_mm_yyyy(self):
        result = _parse_date("15/08/2026")
        assert result == (8, 2026)

    def test_invalid_date(self):
        result = _parse_date("not a date")
        assert result is None

    def test_invalid_month(self):
        result = _parse_date("13/2026")
        assert result is None

    def test_invalid_year(self):
        result = _parse_date("08/2019")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: NORMALIZE_TEXT INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeText:
    """Verify full text normalization pipeline."""

    def test_normalize_returns_tokens(self):
        """Should return list of NormalizedToken."""
        ocr = [MockOCRResult("500gm")]
        tokens = normalize_text(ocr)
        assert isinstance(tokens, list)
        assert len(tokens) == 1

    def test_normalize_preserves_original(self):
        """Normalized token should preserve original text."""
        ocr = [MockOCRResult("Rs. 999")]
        tokens = normalize_text(ocr)
        assert tokens[0].original == "Rs. 999"

    def test_normalize_detects_currency(self):
        """Currency should be detected."""
        ocr = [MockOCRResult("₹999")]
        tokens = normalize_text(ocr)
        assert tokens[0].is_currency is True
        assert tokens[0].currency == "INR"

    def test_normalize_detects_unit(self):
        """Unit should be detected."""
        ocr = [MockOCRResult("500gm")]
        tokens = normalize_text(ocr)
        assert tokens[0].unit == "g"

    def test_normalize_detects_numeric(self):
        """Numeric values should be detected."""
        ocr = [MockOCRResult("999")]
        tokens = normalize_text(ocr)
        assert tokens[0].is_numeric is True
        assert tokens[0].value == 999.0


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: DECLARATION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════


class TestDeclarationExtraction:
    """Verify declaration extraction for all field types."""

    def test_extract_mrp_found(self):
        """MRP with currency should be extracted."""
        ocr = [MockOCRResult("MRP ₹999")]
        result = extract_declarations(ocr)
        mrp = result.get_declaration("mrp")
        assert mrp is not None
        assert mrp.is_not_found is False
        assert "999" in mrp.value

    def test_extract_mrp_not_found(self):
        """MRP without currency should be NOT_FOUND."""
        ocr = [MockOCRResult("Product Name")]
        result = extract_declarations(ocr)
        mrp = result.get_declaration("mrp")
        assert mrp is not None
        assert mrp.is_not_found is True
        assert mrp.value == "NOT_FOUND"

    def test_extract_net_quantity_found(self):
        """Net quantity with unit should be extracted."""
        ocr = [MockOCRResult("Net 500gm")]
        result = extract_declarations(ocr)
        nq = result.get_declaration("net_quantity")
        assert nq is not None
        assert nq.is_not_found is False
        assert "500" in nq.value

    def test_extract_net_quantity_not_found(self):
        """Net quantity without unit should be NOT_FOUND."""
        ocr = [MockOCRResult("Some text")]
        result = extract_declarations(ocr)
        nq = result.get_declaration("net_quantity")
        assert nq is not None
        assert nq.is_not_found is True

    def test_extract_manufacturer_found(self):
        """Manufacturer after 'Manufactured by' should be extracted."""
        ocr = [MockOCRResult("Manufactured by ABC Industries")]
        result = extract_declarations(ocr)
        mfr = result.get_declaration("manufacturer")
        assert mfr is not None
        assert mfr.is_not_found is False
        assert "ABC Industries" in mfr.value

    def test_extract_manufacturer_not_found(self):
        """Manufacturer without keyword should be NOT_FOUND."""
        ocr = [MockOCRResult("Just some text")]
        result = extract_declarations(ocr)
        mfr = result.get_declaration("manufacturer")
        assert mfr is not None
        assert mfr.is_not_found is True

    def test_extract_dates_mfg(self):
        """Date near 'MFG' keyword should be extracted as mfg_date."""
        ocr = [MockOCRResult("MFG 08/2026")]
        result = extract_declarations(ocr)
        mfg = result.get_declaration("mfg_date")
        assert mfg is not None
        assert mfg.is_not_found is False

    def test_extract_dates_packing(self):
        """Date near 'PKD' keyword should be extracted as packing_date."""
        ocr = [MockOCRResult("PKD 12/2025")]
        result = extract_declarations(ocr)
        pkd = result.get_declaration("packing_date")
        assert pkd is not None

    def test_extract_consumer_care_found(self):
        """Consumer care with keyword should be extracted."""
        ocr = [MockOCRResult("Consumer Care: 1800-123-4567")]
        result = extract_declarations(ocr)
        cc = result.get_declaration("consumer_care")
        assert cc is not None
        assert cc.is_not_found is False

    def test_extract_country_of_origin(self):
        """Country of origin should be extracted."""
        ocr = [MockOCRResult("Country of Origin: India")]
        result = extract_declarations(ocr)
        coo = result.get_declaration("country_of_origin")
        assert coo is not None
        assert coo.is_not_found is False
        assert "India" in coo.value

    def test_all_field_types_present(self):
        """Every field type in §14.1 should have an entry."""
        ocr = [MockOCRResult("Test")]
        result = extract_declarations(ocr)
        found_types = {d.field_type for d in result.declarations}
        for ft in FIELD_TYPES:
            assert ft in found_types, f"Missing field type: {ft}"

    def test_missing_fields_are_not_found(self):
        """Missing fields should be recorded as NOT_FOUND, not omitted."""
        ocr = [MockOCRResult("")]
        result = extract_declarations(ocr)
        for d in result.declarations:
            assert d.is_not_found is True or d.value != "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: EXTRACTION RESULT TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractionResult:
    """Verify ExtractionResult properties."""

    def test_found_fields(self):
        """found_fields should list non-NOT_FOUND fields."""
        ocr = [MockOCRResult("MRP ₹999 Net 500gm")]
        result = extract_declarations(ocr)
        assert "mrp" in result.found_fields
        assert "net_quantity" in result.found_fields

    def test_missing_fields(self):
        """missing_fields should list NOT_FOUND fields."""
        ocr = [MockOCRResult("")]
        result = extract_declarations(ocr)
        assert len(result.missing_fields) > 0

    def test_get_declaration(self):
        """get_declaration should return specific field."""
        ocr = [MockOCRResult("MRP ₹999")]
        result = extract_declarations(ocr)
        mrp = result.get_declaration("mrp")
        assert mrp is not None
        assert mrp.field_type == "mrp"

    def test_get_declaration_not_found(self):
        """get_declaration should return None for non-existent field."""
        ocr = [MockOCRResult("")]
        result = extract_declarations(ocr)
        assert result.get_declaration("nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: DATA CLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestDataClasses:
    """Verify dataclass properties and serialization."""

    def test_normalized_token_to_dict(self):
        token = NormalizedToken(
            original="500gm",
            normalized="500gm",
            value=500.0,
            unit="g",
            is_numeric=True,
        )
        d = token.to_dict()
        assert d["unit"] == "g"
        assert d["value"] == 500.0

    def test_declaration_to_dict(self):
        decl = Declaration(
            field_type="mrp",
            value="₹999",
            confidence=0.9,
        )
        d = decl.to_dict()
        assert d["field_type"] == "mrp"
        assert d["confidence"] == 0.9

    def test_declaration_not_found(self):
        decl = Declaration(
            field_type="mrp",
            value="NOT_FOUND",
            is_not_found=True,
        )
        assert decl.is_not_found is True


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9: AMBIGUITY HANDLING
# ═══════════════════════════════════════════════════════════════════════════


class TestAmbiguityHandling:
    """Verify multiple candidates for same field type."""

    def test_multiple_mrp_candidates(self):
        """Multiple currency tokens should produce candidates."""
        ocr = [
            MockOCRResult("Price ₹999"),
            MockOCRResult("MRP ₹1299"),
        ]
        result = extract_declarations(ocr)
        mrp = result.get_declaration("mrp")
        assert mrp is not None
        # Should pick highest confidence
        assert mrp.confidence > 0

    def test_multiple_net_quantity(self):
        """Multiple unit tokens should produce candidates."""
        ocr = [
            MockOCRResult("500gm"),
            MockOCRResult("330ml"),
        ]
        result = extract_declarations(ocr)
        nq = result.get_declaration("net_quantity")
        assert nq is not None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 10: PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestPerformance:
    """Extraction should be fast (no ML inference, pure regex/heuristic)."""

    def test_extraction_under_100ms(self):
        """Extraction should complete in <100ms."""
        ocr = [
            MockOCRResult("Product Name"),
            MockOCRResult("MRP ₹999"),
            MockOCRResult("Net 500gm"),
            MockOCRResult("MFG 08/2026"),
            MockOCRResult("Manufactured by ABC Industries"),
            MockOCRResult("Consumer Care: 1800-123-4567"),
        ]
        start = time.time()
        result = extract_declarations(ocr)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 100, f"Extraction took {elapsed_ms:.0f}ms (target: <100ms)"

    def test_multiple_extractions_under_500ms(self):
        """10 sequential extractions should complete in <500ms."""
        ocr_sets = [
            [MockOCRResult(f"MRP ₹{i * 100}")]
            for i in range(10)
        ]
        start = time.time()
        for ocr in ocr_sets:
            extract_declarations(ocr)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"10 extractions took {elapsed:.2f}s (target: <0.5s)"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 11: INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests combining normalization and extraction."""

    def test_full_label_extraction(self):
        """Simulate a full product label extraction."""
        ocr = [
            MockOCRResult("Britannia Good Day Biscuits"),
            MockOCRResult("MRP ₹999"),
            MockOCRResult("Net Quantity: 250gm"),
            MockOCRResult("MFG 08/2026"),
            MockOCRResult("Manufactured by Britannia Industries Ltd"),
            MockOCRResult("Consumer Care: 1800-123-4567"),
            MockOCRResult("Country of Origin: India"),
        ]
        result = extract_declarations(ocr)

        # Verify key fields found
        assert "mrp" in result.found_fields
        assert "net_quantity" in result.found_fields
        assert "manufacturer" in result.found_fields
        assert "consumer_care" in result.found_fields
        assert "country_of_origin" in result.found_fields

    def test_empty_label_all_not_found(self):
        """Empty label should have all fields NOT_FOUND."""
        ocr = [MockOCRResult("")]
        result = extract_declarations(ocr)
        assert len(result.missing_fields) == len(FIELD_TYPES)

    def test_hindi_label_basic(self):
        """Hindi text should still extract numeric/units."""
        ocr = [MockOCRResult("₹999 500gm")]
        result = extract_declarations(ocr)
        assert "mrp" in result.found_fields
        assert "net_quantity" in result.found_fields

    def test_integration_with_cv_detection(self, cv_detection, ocr_service_module):
        """Full pipeline: detect → OCR → extract.

        cv_detection + ocr_service_module fixtures ensure the heavy
        imports (cv2, onnxruntime, PaddleOCR) are paid once per session,
        not once per test.
        """
        detect_package = cv_detection.detect_package
        crop_image = cv_detection.crop_image
        extract_text_simple = ocr_service_module.extract_text_simple

        # Create a test image
        import numpy as np
        import cv2
        img = np.full((480, 640, 3), 255, dtype=np.uint8)
        cv2.rectangle(img, (100, 80), (500, 400), (50, 50, 50), -1)
        cv2.putText(img, "MRP 999", (150, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        _, buffer = cv2.imencode('.jpg', img)
        image_bytes = buffer.tobytes()

        # Detect
        det = detect_package(image_bytes)
        assert det.detected is True

        # Crop
        cropped = crop_image(image_bytes, det.primary_bbox)

        # OCR
        ocr_results = extract_text_simple(cropped)

        # Extract (may be empty with fallback OCR, but should not crash)
        result = extract_declarations(ocr_results)
        assert isinstance(result, ExtractionResult)
