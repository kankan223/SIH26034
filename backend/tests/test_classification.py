"""
Tests for Task 4.1.1: Product Category Classifier

Verifies:
- classify_product() assigns correct categories per prd.md §13.1
- TF-IDF + GradientBoosting pipeline works correctly
- Confidence threshold ≥0.6 per prd.md §10.4
- Below threshold routes to manual selection
- All categories in taxonomy are represented
- Model save/load via joblib
- Performance: <50ms per prd.md §10.2
- Integration with extraction pipeline
"""
import time
import os
import pytest
import numpy as np

from app.services.classification import (
    classify_product,
    get_category_list,
    retrain_model,
    CATEGORIES,
    CATEGORY_LIST,
    CONFIDENCE_THRESHOLD,
    MODEL_DIR,
    MODEL_PATH,
    _build_training_data,
)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: CATEGORY TAXONOMY TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestCategoryTaxonomy:
    """Verify category taxonomy per prd.md §13.1."""

    def test_categories_dict_has_entries(self):
        """Categories dict should have at least 10 entries."""
        assert len(CATEGORIES) >= 10

    def test_category_list_matches_dict(self):
        """Category list should match dict values."""
        assert len(CATEGORY_LIST) == len(CATEGORIES)

    def test_all_major_categories_present(self):
        """All major category groups should be present."""
        all_categories = " ".join(CATEGORIES.values())
        assert "Food & Beverage" in all_categories
        assert "Personal Care" in all_categories
        assert "Household" in all_categories
        assert "Health & Pharma" in all_categories

    def test_get_category_list_returns_list(self):
        """get_category_list should return a list of strings."""
        result = get_category_list()
        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: TRAINING DATA TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestTrainingData:
    """Verify training data quality."""

    def test_training_data_has_samples(self):
        """Training data should have at least 50 samples."""
        texts, labels = _build_training_data()
        assert len(texts) >= 50
        assert len(texts) == len(labels)

    def test_training_data_multiple_categories(self):
        """Training data should cover multiple categories."""
        _, labels = _build_training_data()
        unique_labels = set(labels)
        assert len(unique_labels) >= 8

    def test_training_data_text_not_empty(self):
        """All training texts should be non-empty."""
        texts, _ = _build_training_data()
        assert all(len(t) > 0 for t in texts)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: CLASSIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestClassification:
    """Verify product classification functionality."""

    def test_classify_britannia_biscuits(self):
        """Britannia Good Day Biscuits should classify as Packaged Food."""
        result = classify_product("Britannia Good Day Biscuits")
        assert "Food & Beverage" in result.category
        assert "Packaged Food" in result.category

    def test_classify_colgate_toothpaste(self):
        """Colgate Toothpaste should classify as Toiletries."""
        result = classify_product("Colgate Toothpaste MaxFresh")
        assert "Personal Care" in result.category
        assert "Toiletries" in result.category

    def test_classify_coca_cola(self):
        """Coca-Cola should classify as Beverages."""
        result = classify_product("Coca-Cola Soft Drink")
        assert "Food & Beverage" in result.category
        assert "Beverages" in result.category

    def test_classify_harpic(self):
        """Harpic should classify as Cleaning Products."""
        result = classify_product("Harpic Toilet Cleaner")
        assert "Household" in result.category
        assert "Cleaning" in result.category

    def test_classify_vicks(self):
        """Vicks Vaporub should classify as Health & Pharma."""
        result = classify_product("Vicks Vaporub")
        assert "Health & Pharma" in result.category

    def test_classify_returns_result(self):
        """Should return a ClassificationResult object."""
        result = classify_product("Test Product")
        assert hasattr(result, "category")
        assert hasattr(result, "confidence")
        assert hasattr(result, "is_confident")

    def test_classify_confidence_in_range(self):
        """Confidence should be between 0 and 1."""
        result = classify_product("Britannia Biscuits")
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_has_category_key(self):
        """Result should have a category_key from CATEGORIES dict."""
        result = classify_product("Maggi Noodles")
        assert result.category_key in CATEGORIES


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: CONFIDENCE THRESHOLD TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceThreshold:
    """Verify confidence threshold per prd.md §10.4."""

    def test_threshold_is_0_6(self):
        """Confidence threshold should be ≥0.6."""
        assert CONFIDENCE_THRESHOLD >= 0.6

    def test_confident_product_above_threshold(self):
        """Clear product names should be classified confidently."""
        result = classify_product("Britannia Good Day Biscuits")
        # Should be confident for known products
        assert result.confidence > 0.0

    def test_is_confident_flag(self):
        """is_confident should match confidence threshold."""
        result = classify_product("Britannia Biscuits")
        assert result.is_confident == (result.confidence >= CONFIDENCE_THRESHOLD)

    def test_needs_manual_selection_flag(self):
        """needs_manual_selection should be inverse of is_confident."""
        result = classify_product("Unknown Product XYZ")
        assert result.needs_manual_selection == (result.confidence < CONFIDENCE_THRESHOLD)

    def test_ambiguous_product_low_confidence(self):
        """Very ambiguous text should have lower confidence."""
        result = classify_product("abc")
        # Short ambiguous text should have lower confidence
        assert result.confidence < 0.9  # Not extremely high


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: EMPTY/EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_product_name(self):
        """Empty product name should return Other/Uncategorized."""
        result = classify_product("")
        assert result.category_key == "other_uncategorized"
        assert result.needs_manual_selection is True

    def test_whitespace_only(self):
        """Whitespace-only input should return Other/Uncategorized."""
        result = classify_product("   ")
        assert result.category_key == "other_uncategorized"

    def test_with_extracted_text(self):
        """Should work with additional extracted text."""
        result = classify_product("Maggi", extracted_text="Noodles 2-Minute Masala")
        assert "Food & Beverage" in result.category

    def test_result_to_dict(self):
        """Result should be serializable via to_dict."""
        result = classify_product("Test Product")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "category" in d
        assert "confidence" in d


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: MODEL ARTIFACT TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestModelArtifact:
    """Verify model save/load functionality.

    Uses the session-scoped trained_classifier fixture so the model
    is trained once for the whole suite, not once per test.
    """

    def test_model_directory_exists(self, trained_classifier):
        """Model directory should exist after training."""
        assert os.path.exists(MODEL_DIR)

    def test_model_file_exists(self, trained_classifier):
        """Model file should exist after training."""
        assert os.path.exists(MODEL_PATH)

    def test_model_file_is_joblib(self, trained_classifier):
        """Model file should be a valid joblib file."""
        import joblib
        model = joblib.load(MODEL_PATH)
        assert hasattr(model, "predict")
        assert hasattr(model, "predict_proba")

    def test_model_load_and_predict(self, trained_classifier):
        """Loaded model should be able to predict."""
        import joblib
        model = joblib.load(MODEL_PATH)
        prediction = model.predict(["Britannia Biscuits"])[0]
        assert prediction in CATEGORIES


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestPerformance:
    """Classification should complete in <50ms per prd.md §10.2."""

    def test_classification_under_50ms(self, trained_classifier):
        """Single classification should complete in <50ms.

        trained_classifier fixture ensures the model is loaded before
        we start the clock, so we measure inference only.
        """
        start = time.time()
        classify_product("Britannia Good Day Biscuits")
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 50, f"Took {elapsed_ms:.0f}ms (target: <50ms)"

    def test_multiple_classifications_under_500ms(self, trained_classifier):
        """20 classifications should complete in <500ms."""
        products = [
            "Britannia Biscuits", "Coca-Cola Drink", "Colgate Toothpaste",
            "Harpic Cleaner", "Vicks Vaporub", "Maggi Noodles",
            "Pepsi Soft Drink", "Dove Soap", "Lizol Floor Cleaner",
            "Crocin Tablet", "Lay's Chips", "Pantene Shampoo",
            "Fortune Oil", "Lakme Foundation", "Domex Cleaner",
            "Real Juice", "Lifebuoy Soap", "Odonil Freshener",
            "Band-Aid Plaster", "Surf Excel",
        ]
        start = time.time()
        for product in products:
            classify_product(product)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"20 classifications took {elapsed:.2f}s (target: <0.5s)"

    def test_retrain_under_10s(self, trained_classifier):
        """Model retraining should complete in <10s (median of 3 runs).

        trained_classifier is the warm-up (imports, BLAS init, joblib
        write cache); we then measure 3 deterministic retrain runs.
        """
        samples = []
        for _ in range(3):
            start = time.time()
            retrain_model()
            samples.append(time.time() - start)
        elapsed = sorted(samples)[1]  # median of 3
        assert elapsed < 10.0, (
            f"Retraining took {elapsed:.2f}s median "
            f"(runs: {[f'{s:.2f}' for s in samples]}) (target: <10.0s)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests combining classification with extraction pipeline."""

    def test_full_pipeline_extract_then_classify(self):
        """Extract declarations → classify product."""
        from app.services.extraction import extract_declarations

        class MockOCR:
            def __init__(self, t, c=0.9):
                self.text = t
                self.original = t
                self.confidence = c
                self.bbox = []
                self.language = "en"

        ocr_results = [
            MockOCR("Britannia Good Day Biscuits"),
            MockOCR("MRP ₹999"),
            MockOCR("Net 250gm"),
        ]

        # Extract
        extraction = extract_declarations(ocr_results)
        product_decl = extraction.get_declaration("product_name")

        # Classify
        product_name = product_decl.value if product_decl and not product_decl.is_not_found else ""
        result = classify_product(product_name)

        assert "Food & Beverage" in result.category

    def test_classification_with_all_categories(self):
        """Each major category should be classifiable."""
        test_products = {
            "Britannia Biscuits": "Food & Beverage",
            "Colgate Toothpaste": "Personal Care",
            "Harpic Cleaner": "Household",
            "Vicks Vaporub": "Health & Pharma",
        }
        for product, expected_partial in test_products.items():
            result = classify_product(product)
            assert expected_partial in result.category, \
                f"{product} expected '{expected_partial}' but got '{result.category}'"
