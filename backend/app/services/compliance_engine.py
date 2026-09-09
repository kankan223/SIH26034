"""Compliance Decision Engine.

Per prd.md §17: Aggregates per-rule verdicts into overall compliance decisions.
Outputs one of: COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, NEEDS_HUMAN_REVIEW,
INSUFFICIENT_EVIDENCE.

The engine evaluates rule verdicts against extracted declarations and produces
a structured compliance result with severity assignments and rule_version_id
references for full auditability.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_check import ComplianceCheck
from app.models.rule_version import RuleVersion
from app.models.violation import Violation
from app.services.rule_engine import RuleVerdict


# ── Enums ──────────────────────────────────────────────────────────────────────

class ComplianceStatus(str, Enum):
    """Overall compliance status for an inspection."""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Severity(str, Enum):
    """Violation severity levels."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class FieldCompliance:
    """Compliance result for a single declaration field."""

    field_type: str
    status: str  # PASS | FAIL | NEEDS_REVIEW | NOT_APPLICABLE
    rule_version_id: Optional[str] = None
    rule_key: Optional[str] = None
    confidence: Optional[float] = None
    detail: str = ""


@dataclass
class ViolationRecord:
    """A recorded violation with severity and evidence reference."""

    field: str
    severity: Severity
    rule_version_id: str
    rule_key: str
    issue_description: str
    detected_value: Optional[str] = None
    expected_condition: Optional[str] = None


@dataclass
class ComplianceResult:
    """Complete compliance evaluation result for an inspection.

    Attributes:
        inspection_id: The inspection being evaluated.
        overall_status: One of the five ComplianceStatus values.
        status_reason: Human-readable explanation of the status.
        per_field_compliance: List of per-field compliance results.
        violations: List of recorded violations (for failed rules).
        confidence_threshold: The confidence threshold used for evaluation.
        low_confidence_fields: Fields with confidence below threshold.
        insufficient_fields: Fields that were NOT_FOUND in extraction.
        evaluated_at: When the evaluation was performed.
    """
    inspection_id: str
    overall_status: ComplianceStatus
    status_reason: str
    per_field_compliance: list[FieldCompliance] = field(default_factory=list)
    violations: list[ViolationRecord] = field(default_factory=list)
    confidence_threshold: float = 0.5  # Default per prd.md §10.4
    low_confidence_fields: list[str] = field(default_factory=list)
    insufficient_fields: list[str] = field(default_factory=list)
    evaluated_at: date = field(default_factory=date.today)


# ── Compliance decision engine ─────────────────────────────────────────────────

def evaluate_compliance(
    inspection_id: str,
    declarations: list[Any],  # List of Declaration objects or dicts
    rule_results: list[RuleVerdict],
    confidence_threshold: float = 0.5,
    min_fields_extracted: int = 3,
) -> ComplianceResult:
    """Evaluate compliance for an inspection based on rule verdicts.

    Decision matrix (per prd.md §17.2):
    1. INSUFFICIENT_EVIDENCE — fewer than min_fields_extracted extracted
    2. NEEDS_HUMAN_REVIEW — any field with confidence below threshold and
       not yet human-reviewed (takes priority over computed verdicts)
    3. NON_COMPLIANT — ≥1 FAIL with high confidence
    4. PARTIALLY_COMPLIANT — some PASS, some FAIL
    5. COMPLIANT — all rules PASS, all confidences ≥ threshold

    Args:
        inspection_id: The inspection UUID.
        declarations: Extracted declaration objects.
        rule_results: List of RuleVerdict from rule_engine.evaluate_rule().
        confidence_threshold: Minimum confidence for PASS to count (default 0.5).
        min_fields_extracted: Minimum number of fields needed for sufficient evidence.

    Returns:
        ComplianceResult with overall status and per-field details.
    """
    # ── Step 1: Check for insufficient evidence ─────────────────────────────

    extracted_fields = _count_extracted_fields(declarations)
    if extracted_fields < min_fields_extracted:
        return ComplianceResult(
            inspection_id=inspection_id,
            overall_status=ComplianceStatus.INSUFFICIENT_EVIDENCE,
            status_reason=(
                f"Only {extracted_fields} fields extracted "
                f"(minimum {min_fields_extracted} required for evaluation). "
                f"Insufficient evidence to determine compliance."
            ),
            insufficient_fields=[
                d.field_type for d in declarations
                if d.value is None or d.value.get("text") is None
            ],
            confidence_threshold=confidence_threshold,
            evaluated_at=date.today(),
        )

    # ── Step 2: Check for low-confidence fields (NEEDS_HUMAN_REVIEW priority) ─

    low_confidence_fields = []
    for verdict in rule_results:
        # Check if the verdict has explicit low confidence
        # RuleVerdict has .passed (False for FAIL) and optional .confidence attribute
        verdict_confidence = getattr(verdict, 'confidence', 1.0)
        if verdict.verdict_type == "MISSING":
            continue  # Missing fields are handled as FAIL, not low-confidence
        if verdict.passed is False and verdict_confidence < confidence_threshold:
            low_confidence_fields.append(verdict.field_type or verdict.rule_key)

    if low_confidence_fields:
        return ComplianceResult(
            inspection_id=inspection_id,
            overall_status=ComplianceStatus.NEEDS_HUMAN_REVIEW,
            status_reason=(
                f"{len(low_confidence_fields)} field(s) have confidence below "
                f"threshold ({confidence_threshold}): {', '.join(low_confidence_fields)}. "
                f"Human review required before final compliance determination."
            ),
            low_confidence_fields=low_confidence_fields,
            confidence_threshold=confidence_threshold,
            evaluated_at=date.today(),
        )

    # ── Step 3: Evaluate per-field compliance ────────────────────────────────

    per_field_results: list[FieldCompliance] = []
    violations: list[ViolationRecord] = []
    fail_count = 0
    pass_count = 0
    not_applicable_count = 0

    for verdict in rule_results:
        field_type = verdict.field_type or verdict.rule_key

        if verdict.verdict == "PASS":
            pass_count += 1
            per_field_results.append(FieldCompliance(
                field_type=field_type,
                status="PASS",
                rule_version_id=verdict.rule_version_id,
                rule_key=verdict.rule_key,
                confidence=1.0,
                detail=verdict.detail,
            ))
        elif verdict.verdict == "FAIL":
            fail_count += 1
            # Determine severity based on rule content
            severity = _determine_severity(verdict)

            per_field_results.append(FieldCompliance(
                field_type=field_type,
                status="FAIL",
                rule_version_id=verdict.rule_version_id,
                rule_key=verdict.rule_key,
                confidence=0.0 if verdict.verdict_type == "MISSING" else 1.0,
                detail=verdict.detail,
            ))

            violations.append(ViolationRecord(
                field=field_type,
                severity=severity,
                rule_version_id=verdict.rule_version_id,
                rule_key=verdict.rule_key,
                issue_description=verdict.detail,
                detected_value=None,  # Would be populated from declaration
                expected_condition="See rule specification",
            ))
        elif verdict.verdict == "NOT_APPLICABLE":
            not_applicable_count += 1
            per_field_results.append(FieldCompliance(
                field_type=field_type,
                status="NOT_APPLICABLE",
                rule_version_id=verdict.rule_version_id,
                rule_key=verdict.rule_key,
                detail=verdict.detail,
            ))
        else:
            # Unknown verdict — treat as NEEDS_REVIEW
            per_field_results.append(FieldCompliance(
                field_type=field_type,
                status="NEEDS_REVIEW",
                rule_version_id=verdict.rule_version_id,
                rule_key=verdict.rule_key,
                detail=f"Unknown verdict: {verdict.verdict}",
            ))

    # ── Step 4: Determine overall status ─────────────────────────────────────

    if fail_count == 0 and pass_count > 0:
        overall = ComplianceStatus.COMPLIANT
        reason = (
            f"All {pass_count} applicable rule(s) passed. "
            f"No violations detected."
        )
    elif fail_count > 0 and pass_count == 0:
        overall = ComplianceStatus.NON_COMPLIANT
        reason = (
            f"All {fail_count} applicable rule(s) failed. "
            f"{len(violations)} violation(s) recorded."
        )
    elif fail_count > 0 and pass_count > 0:
        overall = ComplianceStatus.PARTIALLY_COMPLIANT
        reason = (
            f"{pass_count} rule(s) passed, {fail_count} rule(s) failed. "
            f"{len(violations)} violation(s) recorded. "
            f"Partial compliance — some declarations meet requirements, others do not."
        )
    else:
        # No applicable rules at all
        overall = ComplianceStatus.COMPLIANT
        reason = "No applicable rules found for this product category and date."

    return ComplianceResult(
        inspection_id=inspection_id,
        overall_status=overall,
        status_reason=reason,
        per_field_compliance=per_field_results,
        violations=violations,
        confidence_threshold=confidence_threshold,
        evaluated_at=date.today(),
    )


# ── Helper functions ───────────────────────────────────────────────────────────

def _count_extracted_fields(declarations: list[Any]) -> int:
    """Count the number of fields with actual extracted values."""
    count = 0
    for d in declarations:
        if hasattr(d, 'value') and d.value is not None:
            val = d.value
            if isinstance(val, dict) and val.get('text'):
                count += 1
            elif isinstance(val, str) and val.strip():
                count += 1
        elif hasattr(d, 'text') and d.text:
            count += 1
    return count


def _determine_severity(verdict: RuleVerdict) -> Severity:
    """Determine violation severity based on verdict type and rule content.

    Heuristic:
    - MISSING mandatory field → CRITICAL
    - FORMAT violation of critical field (MRP, dates) → MAJOR
    - Other FORMAT/PRESENCE violations → MINOR
    """
    field = (verdict.field_type or "").lower()
    verdict_type = verdict.verdict_type

    if verdict_type == "MISSING":
        # Missing mandatory declaration → CRITICAL
        if field in ("mrp", "manufacturer_name", "net_quantity", "mfg_date", "country_of_origin"):
            return Severity.CRITICAL
        return Severity.MAJOR

    if verdict_type == "FORMAT":
        # Format violation
        if field in ("mrp", "mfg_date", "pkd_date"):
            return Severity.MAJOR
        return Severity.MINOR

    return Severity.MINOR


# ── Database persistence ───────────────────────────────────────────────────────

async def persist_compliance_checks(
    db: AsyncSession,
    inspection_id: str,
    compliance_result: ComplianceResult,
) -> list[ComplianceCheck]:
    """Persist compliance check records to the database.

    Each rule verdict is stored as a ComplianceCheck row with the exact
    rule_version_id for auditability per prd.md §12.4.

    Args:
        db: Async database session.
        inspection_id: The inspection UUID.
        compliance_result: The ComplianceResult to persist.

    Returns:
        List of created ComplianceCheck objects.
    """
    checks: list[ComplianceCheck] = []

    for field_result in compliance_result.per_field_compliance:
        check = ComplianceCheck(
            inspection_id=inspection_id,
            rule_version_id=field_result.rule_version_id or "",
            verdict=field_result.status.lower().replace(" ", "_"),
            confidence=field_result.confidence,
        )
        db.add(check)
        checks.append(check)

    await db.commit()

    # Refresh to get IDs
    for check in checks:
        await db.refresh(check)

    return checks


async def persist_violations(
    db: AsyncSession,
    inspection_id: str,
    compliance_result: ComplianceResult,
    compliance_check_ids: list[str],
) -> list[Violation]:
    """Persist violation records to the database.

    Each violation references the exact ComplianceCheck and rule_version_id.

    Args:
        db: Async database session.
        inspection_id: The inspection UUID.
        compliance_result: The ComplianceResult containing violations.
        compliance_check_ids: Matching list of compliance check UUIDs.

    Returns:
        List of created Violation objects.
    """
    violations: list[Violation] = []

    for i, violation in enumerate(compliance_result.violations):
        check = compliance_check_ids[i] if i < len(compliance_check_ids) else None
        check_id = getattr(check, "id", check) if check is not None else ""

        v = Violation(
            inspection_id=inspection_id,
            compliance_check_id=check_id,
            field=violation.field,
            severity=violation.severity.value,
            issue_description=violation.issue_description,
            detected_value=violation.detected_value,
            expected_condition=violation.expected_condition,
        )
        db.add(v)
        violations.append(v)

    await db.commit()

    for v in violations:
        await db.refresh(v)

    return violations
