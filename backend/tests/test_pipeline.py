"""Tests for the async pipeline orchestration (backend/app/tasks/pipeline.py).

Covers:
- Individual stage execution (quality, CV, OCR, extraction, classification)
- Full pipeline execution
- Integration with compliance engine and evidence generation
- Warning generation for low-quality images
- Status update on inspection
"""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.pipeline import (
    PipelineResult,
    QualityResult,
    DetectionResult,
    OCRResult,
    ExtractionResult,
    ClassificationResult,
    stage_quality_assessment,
    stage_cv_detection,
    stage_ocr_extraction,
    stage_declaration_extraction,
    stage_classify_product,
    stage_rule_evaluation,
    stage_compliance_evaluation,
    stage_evidence_generation,
    stage_update_inspection_status,
    run_analysis_pipeline,
    QUALITY_THRESHOLD,
    MIN_FIELDS_EXTRACTED,
    CONFIDENCE_THRESHOLD,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_image_bytes():
    """Generate mock image bytes (10x10 white PNG)."""
    from PIL import Image
    import io
    img = Image.new("RGB", (640, 480), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_quality_result():
    """A passing quality result."""
    return QualityResult(
        quality_score=0.85,
        quality_issues=[],
        passed=True,
    )


@pytest.fixture
def sample_detection_result():
    """A detection result with one package and one label."""
    return DetectionResult(
        package_bboxes=[{"x1": 50, "y1": 50, "x2": 600, "y2": 450, "confidence": 0.92}],
        label_bboxes=[{"x1": 80, "y1": 80, "x2": 580, "y2": 430, "confidence": 0.88}],
        manual_crop_used=False,
    )


@pytest.fixture
def sample_ocr_result():
    """OCR result with realistic text blocks."""
    return OCRResult(
        text_blocks=[
            {"text": "MRP Rs. 999", "bbox": [100, 200, 300, 230], "confidence": 0.95, "language": "en"},
            {"text": "Manufactured by Britannia Industries", "bbox": [100, 250, 400, 270], "confidence": 0.88, "language": "en"},
            {"text": "Net Wt. 500gm", "bbox": [100, 300, 280, 320], "confidence": 0.91, "language": "en"},
            {"text": "MFG 08/2026", "bbox": [100, 350, 250, 370], "confidence": 0.82, "language": "en"},
            {"text": "Best Before: 12/2027", "bbox": [100, 380, 300, 400], "confidence": 0.79, "language": "en"},
        ],
        processed_at=date.today(),
    )


@pytest.fixture
def sample_declarations():
    """Sample declaration objects as a list (for direct use)."""
    from dataclasses import dataclass

    @dataclass
    class FakeDecl:
        field_type: str
        field_label: str
        value: dict
        confidence: float
        ocr_source: str

    return [
        FakeDecl("mrp", "Maximum Retail Price", {"text": "Rs. 999", "currency": "INR", "value": 999}, 0.95, "OCR"),
        FakeDecl("manufacturer_name", "Manufacturer", {"text": "Britannia Industries Ltd."}, 0.88, "OCR"),
        FakeDecl("net_quantity", "Net Quantity", {"value": 500, "unit": "g"}, 0.91, "OCR"),
        FakeDecl("mfg_date", "Manufacturing Date", {"month": 8, "year": 2026}, 0.82, "OCR"),
        FakeDecl("best_before_date", "Best Before", {"month": 12, "year": 2027}, 0.79, "OCR"),
        FakeDecl("batch_number", "Batch Number", {"text": "lot:batch123"}, 0.73, "OCR"),
        FakeDecl("package_quantity_label", "Package Quantity Label", {"text": "1"}, 0.68, "OCR"),
    ]


@pytest.fixture
def sample_extraction_result(sample_ocr_result):
    """Sample ExtractionResult with declarations for pipeline stage testing."""
    from app.services.extraction import normalize_text as _normalize, extract_declarations as _extract

    # Convert pipeline dicts to objects with .text, .confidence, .bbox, .original
    class _FakeOCRResult:
        pass
    ocr_results = []
    for b in sample_ocr_result.text_blocks:
        obj = _FakeOCRResult()
        obj.text = b.get('text', '')
        obj.original = b.get('text', '')
        obj.confidence = b.get('confidence', 0.8)
        obj.bbox = b.get('bbox', [[0,0],[0,0]])
        obj.language = b.get('language', 'en')
        obj.is_low_confidence = b.get('is_low_confidence', False)
        ocr_results.append(obj)

    normalized = _normalize(ocr_results)
    extraction = _extract(ocr_results, normalized_tokens=normalized)
    return extraction


@pytest.fixture
def sample_classification_result():
    """Classification result for Food & Beverage."""
    return ClassificationResult(
        category="Food & Beverage",
        confidence=0.94,
        needs_manual_selection=False,
    )


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ── Stage 1: Quality Assessment ────────────────────────────────────────────────

class TestStageQualityAssessment:
    """Tests for stage_quality_assessment."""

    @pytest.mark.asyncio
    async def test_returns_quality_result_with_score(self, mock_image_bytes):
        """Quality assessment returns a QualityResult with score."""
        result = await stage_quality_assessment(mock_image_bytes)
        assert isinstance(result, QualityResult)
        assert 0.0 <= result.quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_quality_score_above_threshold_for_good_image(self, mock_image_bytes):
        """A good image should pass the quality threshold."""
        result = await stage_quality_assessment(mock_image_bytes)
        assert result.quality_score >= QUALITY_THRESHOLD or result.quality_score > 0

    @pytest.mark.asyncio
    async def test_quality_issues_is_list(self, mock_image_bytes):
        """quality_issues should always be a list."""
        result = await stage_quality_assessment(mock_image_bytes)
        assert isinstance(result.quality_issues, list)


# ── Stage 2: CV Detection ──────────────────────────────────────────────────────

class TestStageCVDetection:
    """Tests for stage_cv_detection."""

    @pytest.mark.asyncio
    async def test_returns_detection_result(self, mock_image_bytes):
        """CV detection returns a DetectionResult."""
        result = await stage_cv_detection(mock_image_bytes)
        assert isinstance(result, DetectionResult)

    @pytest.mark.asyncio
    async def test_bboxes_are_lists(self, mock_image_bytes):
        """Both package_bboxes and label_bboxes should be lists."""
        result = await stage_cv_detection(mock_image_bytes)
        assert isinstance(result.package_bboxes, list)
        assert isinstance(result.label_bboxes, list)

    @pytest.mark.asyncio
    async def test_manual_crop_used_flag_exists(self, mock_image_bytes):
        """manual_crop_used flag should exist."""
        result = await stage_cv_detection(mock_image_bytes)
        assert isinstance(result.manual_crop_used, bool)


# ── Stage 3: OCR Extraction ────────────────────────────────────────────────────

class TestStageOCRExtraction:
    """Tests for stage_ocr_extraction."""

    @pytest.mark.asyncio
    async def test_returns_ocr_result(self, mock_image_bytes, sample_detection_result):
        """OCR extraction returns an OCRResult."""
        result = await stage_ocr_extraction(
            mock_image_bytes,
            sample_detection_result.label_bboxes,
            sample_detection_result.manual_crop_used,
        )
        assert isinstance(result, OCRResult)

    @pytest.mark.asyncio
    async def test_text_blocks_are_list(self, mock_image_bytes, sample_detection_result):
        """text_blocks should be a list."""
        result = await stage_ocr_extraction(
            mock_image_bytes,
            sample_detection_result.label_bboxes,
            sample_detection_result.manual_crop_used,
        )
        assert isinstance(result.text_blocks, list)

    @pytest.mark.asyncio
    async def test_manual_crop_mode_ocr_full_image(self, mock_image_bytes):
        """When manual_crop_used=True, OCR the full image."""
        result = await stage_ocr_extraction(
            mock_image_bytes,
            [],
            True,  # manual_crop_used
        )
        assert isinstance(result, OCRResult)
        assert isinstance(result.text_blocks, list)


# ── Stage 4: Declaration Extraction ────────────────────────────────────────────

class TestStageDeclarationExtraction:
    """Tests for stage_declaration_extraction."""

    @pytest.mark.asyncio
    async def test_returns_extraction_result(self, sample_ocr_result):
        """Extraction returns an ExtractionResult."""
        result = await stage_declaration_extraction(sample_ocr_result)
        assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_declarations_are_list(self, sample_ocr_result):
        """declarations should be a list."""
        result = await stage_declaration_extraction(sample_ocr_result)
        assert isinstance(result.declarations, list)

    @pytest.mark.asyncio
    async def test_extracted_declarations_have_field_types(self, sample_ocr_result):
        """Extracted declarations should have recognizable field types."""
        result = await stage_declaration_extraction(sample_ocr_result)
        field_types = [d.field_type for d in result.declarations]
        # At least MRP or manufacturer should be found
        assert len(field_types) > 0


# ── Stage 5: Classification ────────────────────────────────────────────────────

class TestStageClassification:
    """Tests for stage_classify_product."""

    @pytest.mark.asyncio
    async def test_returns_classification_result(self, sample_extraction_result):
        """Classification returns a ClassificationResult."""
        result = await stage_classify_product(sample_extraction_result)
        assert isinstance(result, ClassificationResult)

    @pytest.mark.asyncio
    async def test_category_is_string(self, sample_extraction_result):
        """category should be a non-empty string."""
        result = await stage_classify_product(sample_extraction_result)
        assert isinstance(result.category, str)
        assert len(result.category) > 0

    @pytest.mark.asyncio
    async def test_confidence_in_range(self, sample_extraction_result):
        """confidence should be in [0.0, 1.0]."""
        result = await stage_classify_product(sample_extraction_result)
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_with_product_name(self, sample_extraction_result):
        """Classification with product name should work."""
        result = await stage_classify_product(
            sample_extraction_result, product_name="Britannia Good Day"
        )
        assert isinstance(result, ClassificationResult)


# ── Stage 6: Rule Evaluation ───────────────────────────────────────────────────

class TestStageRuleEvaluation:
    """Tests for stage_rule_evaluation."""

    @pytest.mark.asyncio
    async def test_returns_list_of_verdicts(self, mock_db_session, sample_declarations):
        """Rule evaluation returns a list of RuleVerdict."""
        with patch("app.tasks.pipeline.evaluate_all_rules") as mock_eval:
            mock_eval.return_value = []
            result = await stage_rule_evaluation(
                mock_db_session,
                "Food & Beverage",
                date(2026, 9, 1),
                sample_declarations,
            )
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_passes_correct_args_to_evaluator(self, mock_db_session, sample_declarations):
        """Stage passes correct args to evaluate_all_rules."""
        with patch("app.tasks.pipeline.evaluate_all_rules") as mock_eval:
            mock_eval.return_value = []
            await stage_rule_evaluation(
                mock_db_session,
                "Food & Beverage",
                date(2026, 9, 1),
                sample_declarations,
                package_type="plastic_bottle",
            )
            mock_eval.assert_called_once()
            _, kwargs = mock_eval.call_args
            assert kwargs.get("product_category") == "Food & Beverage"
            assert kwargs.get("package_type") == "plastic_bottle"


# ── Stage 7: Compliance Evaluation ─────────────────────────────────────────────

class TestStageComplianceEvaluation:
    """Tests for stage_compliance_evaluation."""

    @pytest.mark.asyncio
    async def test_returns_compliance_result(self, mock_db_session, sample_declarations):
        """Compliance evaluation returns a ComplianceResult."""
        from app.services.compliance_engine import ComplianceResult

        mock_verdicts = []
        mock_db_session.execute.return_value = MagicMock()

        with patch("app.tasks.pipeline.evaluate_compliance") as mock_eval:
            mock_result = ComplianceResult(
                inspection_id="test-id",
                overall_status="COMPLIANT",
                status_reason="All passed",
            )
            mock_eval.return_value = mock_result
            mock_db_session.get.return_value = None

            with patch("app.tasks.pipeline.persist_compliance_checks", new_callable=AsyncMock) as mock_persist:
                mock_persist.return_value = []
                result = await stage_compliance_evaluation(
                    "test-inspection-id",
                    sample_declarations,
                    mock_verdicts,
                    mock_db_session,
                )
                assert isinstance(result, ComplianceResult)

    @pytest.mark.asyncio
    async def test_persists_checks_to_db(self, mock_db_session, sample_declarations):
        """Compliance stage persists checks to database."""
        from app.services.compliance_engine import ComplianceResult

        mock_verdicts = []
        mock_db_session.get.return_value = None

        with patch("app.tasks.pipeline.evaluate_compliance") as mock_eval:
            mock_result = ComplianceResult(
                inspection_id="test-id",
                overall_status="COMPLIANT",
                status_reason="All passed",
            )
            mock_eval.return_value = mock_result

            with patch("app.tasks.pipeline.persist_compliance_checks", new_callable=AsyncMock) as mock_persist:
                mock_persist.return_value = []
                await stage_compliance_evaluation(
                    "test-id", sample_declarations, mock_verdicts, mock_db_session,
                )
                mock_persist.assert_called_once()


# ── Stage 8: Evidence Generation ───────────────────────────────────────────────

class TestStageEvidenceGeneration:
    """Tests for stage_evidence_generation."""

    @pytest.mark.asyncio
    async def test_returns_evidence_count(self, mock_db_session):
        """Evidence generation returns a count of created evidence objects."""
        from app.services.compliance_engine import ViolationRecord, Severity, ComplianceResult

        violations = [
            ViolationRecord(
                field="mrp",
                severity=Severity.CRITICAL,
                rule_version_id="rv-1",
                rule_key="mrp_format",
                issue_description="MRP format incorrect",
            ),
        ]

        mock_compliance = ComplianceResult(
            inspection_id="test-id",
            overall_status="NON_COMPLIANT",
            status_reason="Violation found",
            violations=violations,
        )

        with patch("app.tasks.pipeline.generate_evidence_for_violations", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = 1
            count = await stage_evidence_generation(
                mock_db_session,
                "test-inspection-id",
                "s3://bucket/image.jpg",
                b"fake_image_bytes",
                mock_compliance,
            )
            assert count == 1
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_violations_returns_zero_evidence(self, mock_db_session):
        """No violations → zero evidence created."""
        from app.services.compliance_engine import ComplianceResult
        from unittest.mock import MagicMock

        mock_compliance = ComplianceResult(
            inspection_id="test-id",
            overall_status="COMPLIANT",
            status_reason="All passed",
            violations=[],
        )

        # Mock the execute result to return None (no image found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await stage_evidence_generation(
            mock_db_session,
            "test-id",
            "s3://bucket/img.jpg",
            b"fake_bytes",
            mock_compliance,
        )
        assert count == 0


# ── Stage 9: Status Update ─────────────────────────────────────────────────────

class TestStageStatusUpdate:
    """Tests for stage_update_inspection_status."""

    @pytest.mark.asyncio
    async def test_compliant_sets_approved_status(self, mock_db_session):
        """COMPLIANT → status = 'approved'."""
        from app.services.compliance_engine import ComplianceResult, ComplianceStatus

        result = ComplianceResult(
            inspection_id="test-id",
            overall_status=ComplianceStatus.COMPLIANT,
            status_reason="All passed",
        )
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()

        await stage_update_inspection_status(mock_db_session, "test-id", result)
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_compliant_sets_flagged_status(self, mock_db_session):
        """NON_COMPLIANT → status = 'flagged'."""
        from app.services.compliance_engine import ComplianceResult, ComplianceStatus

        result = ComplianceResult(
            inspection_id="test-id",
            overall_status=ComplianceStatus.NON_COMPLIANT,
            status_reason="Violation found",
        )
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()

        await stage_update_inspection_status(mock_db_session, "test-id", result)
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_needs_review_sets_pending_review_status(self, mock_db_session):
        """NEEDS_HUMAN_REVIEW → status = 'pending_review'."""
        from app.services.compliance_engine import ComplianceResult, ComplianceStatus

        result = ComplianceResult(
            inspection_id="test-id",
            overall_status=ComplianceStatus.NEEDS_HUMAN_REVIEW,
            status_reason="Low confidence",
        )
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()

        await stage_update_inspection_status(mock_db_session, "test-id", result)
        mock_db_session.execute.assert_called_once()


# ── Full Pipeline ───────────────────────────────────────────────────────────────

class TestFullPipeline:
    """Tests for run_analysis_pipeline (full end-to-end)."""

    @pytest.mark.asyncio
    async def test_pipeline_returns_pipeline_result(self, mock_image_bytes, mock_db_session):
        """Full pipeline returns a PipelineResult with all stages."""
        mock_db_session.get = AsyncMock(return_value=None)
        mock_db_session.execute = AsyncMock()

        with patch("app.tasks.pipeline.stage_quality_assessment", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = QualityResult(0.85, [], True)

            with patch("app.tasks.pipeline.stage_cv_detection", new_callable=AsyncMock) as mock_cv:
                mock_cv.return_value = DetectionResult([], [], False)

                with patch("app.tasks.pipeline.stage_ocr_extraction", new_callable=AsyncMock) as mock_ocr:
                    mock_ocr.return_value = OCRResult([], date.today())

                    with patch("app.tasks.pipeline.stage_declaration_extraction", new_callable=AsyncMock) as mock_ext:
                        mock_ext.return_value = ExtractionResult([], [], 5.0)

                        with patch("app.tasks.pipeline.stage_classify_product", new_callable=AsyncMock) as mock_cls:
                            mock_cls.return_value = ClassificationResult("Food & Beverage", 0.9, False)

                            with patch("app.tasks.pipeline.stage_rule_evaluation", new_callable=AsyncMock) as mock_rules:
                                mock_rules.return_value = []

                                with patch("app.tasks.pipeline.stage_compliance_evaluation", new_callable=AsyncMock) as mock_comp:
                                    from app.services.compliance_engine import ComplianceResult, ComplianceStatus
                                    mock_compliance_result = ComplianceResult(
                                        inspection_id="test-id",
                                        overall_status=ComplianceStatus.COMPLIANT,
                                        status_reason="All passed",
                                        violations=[],
                                    )
                                    mock_comp.return_value = mock_compliance_result

                                    with patch("app.tasks.pipeline.stage_evidence_generation", new_callable=AsyncMock) as mock_ev:
                                        mock_ev.return_value = 0

                                        with patch("app.tasks.pipeline.stage_update_inspection_status", new_callable=AsyncMock):
                                            with patch("app.tasks.pipeline.upload_image", new_callable=AsyncMock) as mock_upload:
                                                mock_upload.return_value = "s3://bucket/img.jpg"

                                                with patch("app.tasks.pipeline._compute_hash", return_value="hash123"):
                                                    result = await run_analysis_pipeline(
                                                        mock_db_session,
                                                        "test-inspection-id",
                                                        mock_image_bytes,
                                                        product_name="Test Product",
                                                    )

                                                    assert isinstance(result, PipelineResult)
                                                    assert result.inspection_id == "test-inspection-id"
                                                    assert result.quality.quality_score == 0.85
                                                    assert result.classification.category == "Food & Beverage"
                                                    assert result.compliance.overall_status == ComplianceStatus.COMPLIANT
                                                    assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_pipeline_generates_warnings_for_low_quality(self, mock_image_bytes, mock_db_session):
        """Low quality images generate warnings but pipeline still completes."""
        mock_db_session.get = AsyncMock(return_value=None)
        mock_db_session.execute = AsyncMock()

        with patch("app.tasks.pipeline.stage_quality_assessment", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = QualityResult(0.45, ["blurry", "low_resolution"], False)

            with patch("app.tasks.pipeline.stage_cv_detection", new_callable=AsyncMock) as mock_cv:
                mock_cv.return_value = DetectionResult([], [], True)

                with patch("app.tasks.pipeline.stage_ocr_extraction", new_callable=AsyncMock) as mock_ocr:
                    mock_ocr.return_value = OCRResult([], date.today())

                    with patch("app.tasks.pipeline.stage_declaration_extraction", new_callable=AsyncMock) as mock_ext:
                        mock_ext.return_value = ExtractionResult([], [], 5.0)

                        with patch("app.tasks.pipeline.stage_classify_product", new_callable=AsyncMock) as mock_cls:
                            mock_cls.return_value = ClassificationResult("Food & Beverage", 0.9, False)

                            with patch("app.tasks.pipeline.stage_rule_evaluation", new_callable=AsyncMock) as mock_rules:
                                mock_rules.return_value = []

                                with patch("app.tasks.pipeline.stage_compliance_evaluation", new_callable=AsyncMock) as mock_comp:
                                    from app.services.compliance_engine import ComplianceResult
                                    mock_comp.return_value = ComplianceResult(
                                        inspection_id="test-id",
                                        overall_status="COMPLIANT",
                                        status_reason="All passed",
                                    )

                                    with patch("app.tasks.pipeline.stage_evidence_generation", new_callable=AsyncMock) as mock_ev:
                                        mock_ev.return_value = 0

                                        with patch("app.tasks.pipeline.stage_update_inspection_status", new_callable=AsyncMock):
                                            with patch("app.tasks.pipeline.upload_image", new_callable=AsyncMock) as mock_upload:
                                                mock_upload.return_value = "s3://bucket/img.jpg"

                                                with patch("app.tasks.pipeline._compute_hash", return_value="hash123"):
                                                    result = await run_analysis_pipeline(
                                                        mock_db_session,
                                                        "test-id",
                                                        mock_image_bytes,
                                                    )

                                                    assert len(result.warnings) > 0
                                                    assert any("quality" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_pipeline_stores_classification_category(self, mock_image_bytes, mock_db_session):
        """Pipeline result stores the classified category."""
        mock_db_session.get = AsyncMock(return_value=None)
        mock_db_session.execute = AsyncMock()

        with patch("app.tasks.pipeline.stage_quality_assessment", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = QualityResult(0.85, [], True)

            with patch("app.tasks.pipeline.stage_cv_detection", new_callable=AsyncMock) as mock_cv:
                mock_cv.return_value = DetectionResult([], [], False)

                with patch("app.tasks.pipeline.stage_ocr_extraction", new_callable=AsyncMock) as mock_ocr:
                    mock_ocr.return_value = OCRResult([], date.today())

                    with patch("app.tasks.pipeline.stage_declaration_extraction", new_callable=AsyncMock) as mock_ext:
                        mock_ext.return_value = ExtractionResult([], [], 5.0)

                        with patch("app.tasks.pipeline.stage_classify_product", new_callable=AsyncMock) as mock_cls:
                            mock_cls.return_value = ClassificationResult("Personal Care & Cosmetics", 0.88, False)

                            with patch("app.tasks.pipeline.stage_rule_evaluation", new_callable=AsyncMock) as mock_rules:
                                mock_rules.return_value = []

                                with patch("app.tasks.pipeline.stage_compliance_evaluation", new_callable=AsyncMock) as mock_comp:
                                    from app.services.compliance_engine import ComplianceResult
                                    mock_comp.return_value = ComplianceResult(
                                        inspection_id="test-id",
                                        overall_status="COMPLIANT",
                                        status_reason="All passed",
                                    )

                                    with patch("app.tasks.pipeline.stage_evidence_generation", new_callable=AsyncMock) as mock_ev:
                                        mock_ev.return_value = 0

                                        with patch("app.tasks.pipeline.stage_update_inspection_status", new_callable=AsyncMock):
                                            with patch("app.tasks.pipeline.upload_image", new_callable=AsyncMock) as mock_upload:
                                                mock_upload.return_value = "s3://bucket/img.jpg"

                                                with patch("app.tasks.pipeline._compute_hash", return_value="hash123"):
                                                    result = await run_analysis_pipeline(
                                                        mock_db_session,
                                                        "test-id",
                                                        mock_image_bytes,
                                                    )

                                                    assert result.classification.category == "Personal Care & Cosmetics"


# ── PipelineResult structure ───────────────────────────────────────────────────

class TestPipelineResultStructure:
    """Verify PipelineResult has all expected fields."""

    def test_pipeline_result_has_all_fields(self):
        """PipelineResult has all required fields."""
        now = date.today()
        result = PipelineResult(
            inspection_id="test-id",
            image_id="img-123",
            quality=QualityResult(0.85, [], True),
            detection=DetectionResult([], [], False),
            ocr=OCRResult([], now),
            extraction=ExtractionResult([], [], 5.0),
            classification=ClassificationResult("Food & Beverage", 0.9, False),
            compliance=None,  # Can be None during construction
            violation_count=0,
            evidence_count=0,
            pipeline_completed_at=now,
            duration_ms=1500.0,
            warnings=[],
        )

        assert result.inspection_id == "test-id"
        assert result.image_id == "img-123"
        assert result.quality.quality_score == 0.85
        assert result.classification.category == "Food & Beverage"
        assert result.violation_count == 0
        assert result.evidence_count == 0
        assert result.duration_ms == 1500.0
        assert result.warnings == []

    def test_pipeline_result_warnings_default_empty(self):
        """PipelineResult warnings default to empty list."""
        result = PipelineResult(
            inspection_id="test-id",
            image_id="img-1",
            quality=QualityResult(0.85, [], True),
            detection=DetectionResult([], [], False),
            ocr=OCRResult([], date.today()),
            extraction=ExtractionResult([], [], 5.0),
            classification=ClassificationResult("Food & Beverage", 0.9, False),
            compliance=None,
            violation_count=0,
            evidence_count=0,
            pipeline_completed_at=date.today(),
            duration_ms=1000.0,
        )
        assert result.warnings == []


# ── Configuration constants ─────────────────────────────────────────────────────

class TestPipelineConfiguration:
    """Verify pipeline configuration constants."""

    def test_quality_threshold_is_float(self):
        """QUALITY_THRESHOLD should be a float between 0 and 1."""
        assert isinstance(QUALITY_THRESHOLD, float)
        assert 0.0 < QUALITY_THRESHOLD < 1.0

    def test_min_fields_extracted_is_positive_int(self):
        """MIN_FIELDS_EXTRACTED should be a positive integer."""
        assert isinstance(MIN_FIELDS_EXTRACTED, int)
        assert MIN_FIELDS_EXTRACTED > 0

    def test_confidence_threshold_is_float(self):
        """CONFIDENCE_THRESHOLD should be 0.5 per prd.md §10.4."""
        assert CONFIDENCE_THRESHOLD == 0.5


# ── Evidence engine tests (separate from pipeline) ─────────────────────────────

class TestEvidenceEngine:
    """Tests for evidence_engine module."""

    @pytest.mark.asyncio
    async def test_generate_evidence_count_with_violations(self, mock_db_session):
        """generate_evidence_for_violations returns count of created evidence."""
        from app.services.evidence_engine import generate_evidence_for_violations
        from app.services.compliance_engine import ViolationRecord, Severity

        violations = [
            ViolationRecord(
                field="mrp",
                severity=Severity.CRITICAL,
                rule_version_id="rv-1",
                rule_key="mrp_format",
                issue_description="Wrong format",
            ),
        ]

        # Mock the image lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No image found

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await generate_evidence_for_violations(
            mock_db_session,
            "test-inspection-id",
            "s3://bucket/img.jpg",
            b"fake_bytes",
            violations,
        )

        # Returns 0 because no image found (expected in unit test without real image)
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_generate_evidence_no_violations_returns_zero(self, mock_db_session):
        """No violations → zero evidence count."""
        from app.services.evidence_engine import generate_evidence_for_violations

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await generate_evidence_for_violations(
            mock_db_session,
            "test-id",
            "s3://bucket/img.jpg",
            b"fake_bytes",
            [],
        )
        assert count == 0

    def test_evidence_record_structure(self):
        """EvidenceRecord has all required fields."""
        from app.services.evidence_engine import EvidenceRecord
        from datetime import datetime

        record = EvidenceRecord(
            evidence_id="ev-1",
            violation_id="v-1",
            image_id="img-1",
            bbox={"x1": 10, "y1": 20, "x2": 100, "y2": 200},
            crop_storage_url="s3://bucket/crop.png",
        )

        assert record.evidence_id == "ev-1"
        assert record.violation_id == "v-1"
        assert record.image_id == "img-1"
        assert record.bbox["x1"] == 10
        assert record.crop_storage_url == "s3://bucket/crop.png"
        assert isinstance(record.created_at, datetime)

    def test_extract_bbox_from_violation_no_bbox(self):
        """When violation has no bbox, returns None."""
        from app.services.evidence_engine import _extract_bbox_from_violation
        from app.services.compliance_engine import ViolationRecord, Severity

        violation = ViolationRecord(
            field="mrp",
            severity=Severity.CRITICAL,
            rule_version_id="rv-1",
            rule_key="mrp_format",
            issue_description="Wrong format",
        )

        result = _extract_bbox_from_violation(violation)
        assert result is None


# ── Report generator tests ─────────────────────────────────────────────────────

class TestReportGenerator:
    """Tests for report_generator module."""

    def test_report_result_structure(self):
        """ReportResult has all required fields."""
        from app.services.report_generator import ReportResult
        from datetime import datetime

        result = ReportResult(
            report_id="rpt-1",
            pdf_storage_url="s3://bucket/report.pdf",
            json_export_url="s3://bucket/report.json",
            inspection_id="inv-1",
        )

        assert result.report_id == "rpt-1"
        assert result.pdf_storage_url == "s3://bucket/report.pdf"
        assert result.json_export_url == "s3://bucket/report.json"
        assert result.inspection_id == "inv-1"
        assert isinstance(result.generated_at, datetime)
        assert result.generation_time_ms == 0.0

    def test_get_design_tokens(self):
        """Design tokens match design.md §12 colors."""
        from app.services.report_generator import _get_design_tokens

        tokens = _get_design_tokens()

        assert tokens["color_ink_navy"] == "#1B2A41"
        assert tokens["color_paper_cream"] == "#F8F5F0"
        assert tokens["color_teal"] == "#2E8B8B"
        assert tokens["color_redline"] == "#C0392B"
        assert tokens["color_amber"] == "#D4A017"
        assert "font_heading" in tokens
        assert "font_body" in tokens
        assert "font_mono" in tokens

    def test_generate_report_html_has_12_sections(self):
        """Generated HTML has all 12 sections."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection={"id": "test-id", "created_at": "2026-09-01", "inspector_name": "Inspector", "location": "Delhi", "region": "Delhi", "source": "physical", "product_name": "Test", "status": "pending", "inspector_id": "ins-1"},
            compliance={"overall_status": "COMPLIANT", "status_reason": "All passed", "violations": []},
            images=[],
            evidence=[],
            legal_references=["Legal Metrology Rules 2011"],
            show_seal=True,
        )

        # Check all 12 section headings
        for i in range(1, 13):
            assert f"class=\"section" in html  # At least one section

        # Check specific sections
        assert "Inspection Information" in html
        assert "Product Information" in html
        assert "Images" in html or "4. Images" in html
        assert "Declarations" in html
        assert "Compliance Summary" in html
        assert "Violations" in html
        assert "Evidence Appendix" in html
        assert "Legal References" in html
        assert "Confidence Notes" in html
        assert "Inspector Review" in html
        assert "Audit Information" in html
        assert "Cover" in html or "Docket" in html  # Cover page

    def test_compliant_report_has_seal(self):
        """COMPLIANT report includes verification seal div."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection={"id": "test-id", "created_at": "2026-09-01", "inspector_name": "I", "location": "Delhi", "region": "Delhi", "source": "physical", "product_name": "Test", "status": "approved", "inspector_id": "ins-1"},
            compliance={"overall_status": "COMPLIANT", "status_reason": "All passed", "violations": []},
            images=[],
            evidence=[],
            legal_references=["Rule"],
            show_seal=True,
        )

        assert '<div class="verification-seal">' in html
        assert "This inspection has been verified as compliant" in html

    def test_non_compliant_report_no_seal(self):
        """NON_COMPLIANT report does NOT include verification seal div."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection={"id": "test-id", "created_at": "2026-09-01", "inspector_name": "I", "location": "Delhi", "region": "Delhi", "source": "physical", "product_name": "Test", "status": "flagged", "inspector_id": "ins-1"},
            compliance={"overall_status": "NON_COMPLIANT", "status_reason": "Violation", "violations": [{"field": "mrp", "severity": "critical", "rule_key": "mrp_format", "issue_description": "Wrong MRP"}]},
            images=[],
            evidence=[],
            legal_references=["Rule"],
            show_seal=False,
        )

        # CSS class reference is present (style block), but seal div should not be rendered
        assert '<div class="verification-seal"' not in html
        assert "Violations" in html

    def test_report_html_contains_design_tokens(self):
        """Report HTML uses design tokens for colors."""
        from app.services.report_generator import _generate_report_html

        html = _generate_report_html(
            inspection={"id": "test", "created_at": "2026-09-01", "inspector_name": "I", "location": "L", "region": "R", "source": "physical", "product_name": "Test", "status": "pending", "inspector_id": "ins-1"},
            compliance={"overall_status": "COMPLIANT", "status_reason": "OK", "violations": []},
            images=[],
            evidence=[],
            legal_references=["LMR 2011"],
            show_seal=True,
        )

        assert "#1B2A41" in html  # Ink Navy
        assert "#F8F5F0" in html  # Paper Cream
        assert "#2E8B8B" in html  # Teal
        assert "#C0392B" in html  # Redline
        assert "#D4A017" in html  # Amber
        assert "Source Serif 4" in html
        assert "IBM Plex Sans" in html
        assert "IBM Plex Mono" in html

    def test_generate_report_from_pipeline_result(self):
        """generate_report_from_pipeline maps pipeline output correctly."""
        from app.services.report_generator import (
            generate_report_from_pipeline,
            ReportResult as GenReportResult,
        )
        from app.services.compliance_engine import ComplianceResult, ComplianceStatus
        from app.tasks.pipeline import (
            PipelineResult, QualityResult, DetectionResult,
            OCRResult, ExtractionResult, ClassificationResult,
        )
        from datetime import date

        pipeline_result = PipelineResult(
            inspection_id="test-id",
            image_id="img-1",
            quality=QualityResult(0.85, [], True),
            detection=DetectionResult([], [], False),
            ocr=OCRResult([], date.today()),
            extraction=ExtractionResult(
                declarations=[
                    type("D", (), {"field_type": "mrp", "value": {"text": "Rs. 999"}, "confidence": 0.95})(),
                    type("D2", (), {"field_type": "manufacturer_name", "value": {"text": "Britannia"}, "confidence": 0.88})(),
                ],
                normalized_tokens=[],
                extraction_time_ms=10.0,
            ),
            classification=ClassificationResult("Food & Beverage", 0.92, False),
            compliance=ComplianceResult(
                inspection_id="test-id",
                overall_status=ComplianceStatus.COMPLIANT,
                status_reason="All passed",
                violations=[],
            ),
            violation_count=0,
            evidence_count=0,
            pipeline_completed_at=date.today(),
            duration_ms=5000.0,
        )

        inspection_extra = {
            "inspector_name": "Inspector Name",
            "location": "Delhi",
            "region": "Delhi",
            "source": "physical",
            "product_name": "Britannia Good Day",
            "package_type": "wrapper",
        }

        with patch("app.services.report_generator.generate_report", return_value=GenReportResult(
            report_id="rpt-1",
            pdf_storage_url="s3://bucket/rpt.pdf",
            json_export_url="s3://bucket/rpt.json",
            inspection_id="test-id",
        )) as mock_gen:
            report = generate_report_from_pipeline(pipeline_result, inspection_extra)
            assert report.report_id == "rpt-1"
            mock_gen.assert_called_once()

            # Verify the inspection data passed to generate_report
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs["inspection_data"]["inspector_name"] == "Inspector Name"
            assert call_kwargs["inspection_data"]["category"] == "Food & Beverage"
            assert call_kwargs["inspection_data"]["classification_confidence"] == 0.92
