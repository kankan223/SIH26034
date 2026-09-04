"""Async pipeline orchestration for compliance checking.

Per prd.md §22 (Processing Screen workflow):
1. Image quality assessment → quality_score + issues
2. CV detection (YOLOv8n) → package bboxes + label bboxes
3. OCR extraction (PaddleOCR) → text with bboxes + confidence
4. Declaration extraction → structured fields
5. Product classification → category
6. Rule engine evaluation → per-rule verdicts
7. Compliance engine → overall status + violations
8. Evidence generation → bbox-grounded crops per violation
9. Status update on inspection

Pipeline is async and designed to run as an RQ background job.
Each stage is independent and can be retried individually.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inspection import Inspection
from app.models.declaration import Declaration
from app.services.rule_engine import (
    get_applicable_rules,
    evaluate_all_rules,
    RuleVerdict,
)
from app.services.compliance_engine import (
    evaluate_compliance,
    persist_compliance_checks,
    persist_violations,
    ComplianceResult,
)
from app.services.evidence_engine import generate_evidence_for_violations
from app.services.storage import upload_image
from app.services.image_processing import assess_quality
from app.core.config import settings


# ── Pipeline stage results ─────────────────────────────────────────────────────

@dataclass
class QualityResult:
    """Output from image quality assessment stage."""
    quality_score: float
    quality_issues: list[str]
    passed: bool  # quality_score >= quality_threshold


@dataclass
class DetectionResult:
    """Output from CV detection stage."""
    package_bboxes: list[dict[str, Any]]  # [{x1, y1, x2, y2, confidence}]
    label_bboxes: list[dict[str, Any]]
    manual_crop_used: bool  # True if no package detected, fell back to full image


@dataclass
class OCRResult:
    """Output from OCR extraction stage."""
    text_blocks: list[dict[str, Any]]  # [{text, bbox, confidence, language}]
    processed_at: date


@dataclass
class ExtractionResult:
    """Output from declaration extraction stage."""
    declarations: list[Declaration]
    normalized_tokens: list[dict[str, Any]]
    extraction_time_ms: float


@dataclass
class ClassificationResult:
    """Output from product classification stage."""
    category: str
    confidence: float
    needs_manual_selection: bool


@dataclass
class PipelineResult:
    """Complete output of the analysis pipeline.

    Aggregates all stage results plus the final compliance determination.
    """
    inspection_id: str
    image_id: str
    quality: QualityResult
    detection: DetectionResult
    ocr: OCRResult
    extraction: ExtractionResult
    classification: ClassificationResult
    compliance: ComplianceResult
    violation_count: int
    evidence_count: int
    pipeline_completed_at: date
    duration_ms: float

    # Stages that had issues (for UI display)
    warnings: list[str] = field(default_factory=list)


# ── Pipeline configuration ─────────────────────────────────────────────────────

# Minimum quality score to proceed without warning
QUALITY_THRESHOLD = 0.7

# Minimum number of fields needed for compliance evaluation
MIN_FIELDS_EXTRACTED = 3

# Confidence threshold for rule evaluation (per prd.md §10.4)
CONFIDENCE_THRESHOLD = 0.5


# ── Pipeline stages (individual, testable, retryable) ──────────────────────────

async def stage_quality_assessment(
    image_bytes: bytes,
) -> QualityResult:
    """Stage 1: Assess image quality (blur, exposure, resolution).

    Returns QualityResult with score and issues list.
    """
    from app.services.image_processing import assess_quality as _assess

    result = _assess(image_bytes)
    passed = result.quality_score >= QUALITY_THRESHOLD

    quality_issues = result.quality_issues or []
    return QualityResult(
        quality_score=result.quality_score,
        quality_issues=quality_issues,
        passed=passed,
    )


async def stage_cv_detection(
    image_bytes: bytes,
) -> DetectionResult:
    """Stage 2: Detect package and label regions via YOLOv8n.

    Returns DetectionResult with bboxes. Falls back to full-image
    mode if no package is detected (manual_crop_used=True).
    """
    from app.services.cv_detection import (
        detect_package as _detect_package,
        detect_label as _detect_label,
    )

    # cv_detection returns its own DetectionResult with .bboxes (list of BBox)
    cv_result = _detect_package(image_bytes)
    manual_crop_used = cv_result.manual_crop_used

    # Convert cv_detection BBox list to dict list for pipeline
    package_bboxes = [b.to_dict() for b in cv_result.bboxes]

    # If no package detected, label region is full image
    if manual_crop_used:
        label_bboxes = []
    else:
        # Use primary package bbox for label detection
        primary = cv_result.primary_bbox
        if primary:
            cv_label_result = _detect_label(image_bytes, primary)
            label_bboxes = [b.to_dict() for b in cv_label_result.bboxes]
        else:
            label_bboxes = []

    return DetectionResult(
        package_bboxes=package_bboxes,
        label_bboxes=label_bboxes,
        manual_crop_used=manual_crop_used,
    )


async def stage_ocr_extraction(
    image_bytes: bytes,
    label_bboxes: list[dict[str, Any]],
    manual_crop_used: bool,
) -> OCRResult:
    """Stage 3: Extract text via PaddleOCR.

    If manual_crop_used, OCR the full image. Otherwise, OCR each label bbox.
    Returns list of text blocks with bboxes, confidence, and language.
    """
    import time
    from app.services.ocr_service import extract_text as _extract_text

    start = time.time()

    if manual_crop_used:
        # OCR full image — returns OCRResponse with .results list
        ocr_response = _extract_text(image_bytes)
        # Convert ocr_service.OCRResult to pipeline dict format
        text_blocks = [_ocr_result_to_dict(r) for r in ocr_response.results]
    else:
        # OCR each label region (crop + OCR)
        text_blocks = []
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        for bbox in label_bboxes:
            cropped = img.crop((
                bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
            ))
            cropped_bytes = io.BytesIO()
            cropped.save(cropped_bytes, format="PNG")
            cropped_response = _extract_text(cropped_bytes.getvalue())
            text_blocks.extend([_ocr_result_to_dict(r) for r in cropped_response.results])

    elapsed_ms = (time.time() - start) * 1000

    return OCRResult(
        text_blocks=text_blocks,
        processed_at=date.today(),
    )


async def stage_declaration_extraction(
    ocr_result: OCRResult,
) -> ExtractionResult:
    """Stage 4: Normalize OCR text and extract declarations.

    Returns structured Declaration objects for each field type.
    """
    import time
    from app.services.extraction import (
        normalize_text as _normalize,
        extract_declarations as _extract,
    )

    start = time.time()

    # Convert pipeline dicts back to ocr_service.OCRResult-like objects
    # for the extraction module which expects .text, .confidence, .bbox attributes
    ocr_service_results = [_dict_to_ocr_result(b) for b in ocr_result.text_blocks]

    normalized = _normalize(ocr_service_results)
    extraction_result = _extract(ocr_service_results, normalized_tokens=normalized)

    elapsed_ms = (time.time() - start) * 1000

    # Convert extraction.Declaration to pipeline format
    # Pipeline expects declarations to have .field_type, .value, .confidence
    # The extraction module returns extraction.ExtractionResult with .declarations
    return ExtractionResult(
        declarations=extraction_result.declarations,
        normalized_tokens=normalized,
        extraction_time_ms=elapsed_ms,
    )


async def stage_classify_product(
    extraction_result: ExtractionResult,
    product_name: Optional[str] = None,
) -> ClassificationResult:
    """Stage 5: Classify product into category.

    Uses TF-IDF + GradientBoosting classifier. Falls back to
    manual selection if confidence < 0.6.
    """
    from app.services.classification import classify_product as _classify

    # Use declaration values as text for classification
    declaration_text = " ".join(
        d.value.get("text", str(d.value))
        if isinstance(d.value, dict) else str(d.value)
        for d in extraction_result.declarations
        if d.value and str(d.value) != "NOT_FOUND"
    )

    result = _classify(
        product_name=product_name or "",
        extracted_text=declaration_text,
    )

    return ClassificationResult(
        category=result.category,
        confidence=result.confidence,
        needs_manual_selection=result.needs_manual_selection,
    )


async def stage_rule_evaluation(
    db: AsyncSession,
    category: str,
    inspection_date: date,
    declarations: list[Declaration],
    package_type: Optional[str] = None,
) -> list[RuleVerdict]:
    """Stage 6: Evaluate all applicable rules against declarations.

    Returns list of RuleVerdict objects, each referencing exact
    rule_versions.id for auditability.
    """
    verdicts = evaluate_all_rules(
        db=db,
        category=category,
        inspection_date=inspection_date,
        declarations=declarations,
        product_category=category,
        package_type=package_type,
    )
    return verdicts


async def stage_compliance_evaluation(
    inspection_id: str,
    declarations: list[Declaration],
    rule_results: list[RuleVerdict],
    db: AsyncSession,
) -> ComplianceResult:
    """Stage 7: Aggregate rule verdicts into overall compliance status.

    Persists compliance_checks and violations to database.
    Returns ComplianceResult with overall status.
    """
    result = evaluate_compliance(
        inspection_id=inspection_id,
        declarations=declarations,
        rule_results=rule_results,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        min_fields_extracted=MIN_FIELDS_EXTRACTED,
    )

    # Persist to DB
    check_ids = await persist_compliance_checks(db, inspection_id, result)

    if result.violations:
        await persist_violations(db, inspection_id, result, check_ids)

    return result


async def stage_evidence_generation(
    db: AsyncSession,
    inspection_id: str,
    image_storage_url: str,
    image_bytes: bytes,
    compliance_result: ComplianceResult,
) -> int:
    """Stage 8: Generate evidence for each violation.

    Crops image at violation bbox and uploads to MinIO.
    Returns count of evidence objects created.
    """
    count = await generate_evidence_for_violations(
        db=db,
        inspection_id=inspection_id,
        image_storage_url=image_storage_url,
        image_bytes=image_bytes,
        violations=compliance_result.violations,
    )
    return count


async def stage_update_inspection_status(
    db: AsyncSession,
    inspection_id: str,
    compliance_result: ComplianceResult,
) -> None:
    """Stage 9: Update inspection status based on compliance result.

    COMPLIANT → status='approved'
    NON_COMPLIANT/PARTIALLY_COMPLIANT → status='flagged'
    NEEDS_HUMAN_REVIEW → status='pending_review'
    INSUFFICIENT_EVIDENCE → status='insufficient'
    """
    from sqlalchemy import text

    status_map = {
        "COMPLIANT": "approved",
        "NON_COMPLIANT": "flagged",
        "PARTIALLY_COMPLIANT": "flagged",
        "NEEDS_HUMAN_REVIEW": "pending_review",
        "INSUFFICIENT_EVIDENCE": "insufficient",
    }

    new_status = status_map.get(
        compliance_result.overall_status.value, "pending"
    )

    await db.execute(
        text(
            "UPDATE inspections SET status = :status WHERE id = :id"
        ),
        {"status": new_status, "id": inspection_id},
    )
    await db.commit()


# ── Full pipeline execution ────────────────────────────────────────────────────

async def run_analysis_pipeline(
    db: AsyncSession,
    inspection_id: str,
    image_bytes: bytes,
    product_name: Optional[str] = None,
    package_type: Optional[str] = None,
) -> PipelineResult:
    """Execute the full compliance analysis pipeline end-to-end.

    Pipeline stages:
    1. Image quality assessment
    2. CV detection (YOLOv8n)
    3. OCR extraction (PaddleOCR)
    4. Declaration extraction
    5. Product classification
    6. Rule engine evaluation
    7. Compliance evaluation
    8. Evidence generation
    9. Inspection status update

    Args:
        db: Async database session.
        inspection_id: The inspection UUID.
        image_bytes: Raw image bytes.
        product_name: Optional product name for classification.
        package_type: Optional package type for rule filtering.

    Returns:
        PipelineResult with all stage outputs and compliance determination.

    Raises:
        RuntimeError: If a critical stage fails (quality too low is not
            critical — it generates a warning).
    """
    import time
    from datetime import date

    overall_start = time.time()
    warnings: list[str] = []

    # Stage 1: Quality assessment
    quality = await stage_quality_assessment(image_bytes)
    if not quality.passed:
        warnings.append(
            f"Image quality score {quality.quality_score:.2f} below "
            f"threshold {QUALITY_THRESHOLD:.2f}. "
            f"Issues: {', '.join(quality.quality_issues)}"
        )

    # Upload image to MinIO (always, even if quality is low)
    content_hash = _compute_hash(image_bytes)
    storage_url = await upload_image(image_bytes, content_hash)

    # Stage 2: CV detection
    detection = await stage_cv_detection(image_bytes)

    # Stage 3: OCR
    ocr = await stage_ocr_extraction(
        image_bytes, detection.label_bboxes, detection.manual_crop_used
    )

    # Stage 4: Extraction
    extraction = await stage_declaration_extraction(ocr)

    # Stage 5: Classification
    classification = await stage_classify_product(extraction, product_name)

    # Look up inspection to get date
    inspection = await db.get(Inspection, inspection_id)
    inspection_date = (
        inspection.created_at.date() if inspection else date.today()
    )

    # Stage 6: Rule evaluation
    rule_results = await stage_rule_evaluation(
        db, classification.category, inspection_date,
        extraction.declarations, package_type,
    )

    # Stage 7: Compliance evaluation
    compliance = await stage_compliance_evaluation(
        inspection_id, extraction.declarations, rule_results, db,
    )

    # Stage 8: Evidence generation
    evidence_count = await stage_evidence_generation(
        db, inspection_id, storage_url, image_bytes, compliance,
    )

    # Stage 9: Status update
    await stage_update_inspection_status(db, inspection_id, compliance)

    overall_duration_ms = (time.time() - overall_start) * 1000

    return PipelineResult(
        inspection_id=inspection_id,
        image_id="",
        quality=quality,
        detection=detection,
        ocr=ocr,
        extraction=extraction,
        classification=classification,
        compliance=compliance,
        violation_count=len(compliance.violations),
        evidence_count=evidence_count,
        pipeline_completed_at=date.today(),
        duration_ms=overall_duration_ms,
        warnings=warnings,
    )


def _ocr_result_to_dict(ocr_result: Any) -> dict[str, Any]:
    """Convert ocr_service.OCRResult to pipeline dict format.

    Handles both ocr_service.OCRResult dataclass and plain dicts.
    """
    if hasattr(ocr_result, 'to_dict'):
        return ocr_result.to_dict()
    if hasattr(ocr_result, 'text'):
        return {
            'text': ocr_result.text,
            'bbox': ocr_result.bbox,
            'confidence': getattr(ocr_result, 'confidence', 0),
            'language': getattr(ocr_result, 'language', 'unknown'),
            'is_low_confidence': getattr(ocr_result, 'is_low_confidence', False),
        }
    # Already a dict
    return dict(ocr_result)


def _dict_to_ocr_result(data: dict[str, Any]) -> Any:
    """Convert pipeline dict to ocr_service.OCRResult-like object.

    Creates a simple object with .text, .confidence, .bbox, .language,
    .original attributes that the extraction module expects.
    """
    class _FakeOCRResult:
        pass
    obj = _FakeOCRResult()
    obj.text = data.get('text', '')
    obj.original = data.get('text', '')  # extraction.py reads .original
    obj.confidence = data.get('confidence', 0)
    obj.bbox = data.get('bbox', [])
    obj.language = data.get('language', 'unknown')
    obj.is_low_confidence = data.get('is_low_confidence', False)
    return obj


def _compute_hash(data: bytes) -> str:
    """Compute SHA-256 hash of image bytes for deduplication."""
    import hashlib
    return hashlib.sha256(data).hexdigest()
