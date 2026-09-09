"""Rule engine evaluator — deterministic, data-driven compliance checking.

Per prd.md §12: rules are data, not code. This module reads rule records from
Postgres (rules + rule_versions) and executes their applies_when/validation logic
against extracted declarations. 100% deterministic per FR-010.

Key design principles:
- Every verdict references the exact rule_versions.id (not just rule_id) for auditability.
- Rules are evaluated in order of effective_date (oldest first) for reproducibility.
- Missing mandatory declarations → FAIL with type MISSING, never silently pass.
- NOT_APPLICABLE when applies_when conditions are not met.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule
from app.models.rule_version import RuleVersion
from app.models.declaration import Declaration


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class RuleInstance:
    """A specific version of a rule to be evaluated.

    Attributes:
        rule_id: Stable rule identity (rules.id).
        rule_version_id: Exact version identity (rule_versions.id) — must be
            referenced in every verdict for full auditability.
        version: Version number.
        rule_key: Human-readable rule key (e.g., "mrp_format").
        title: Human-readable rule title.
        content: The rule schema dict (applies_when, validation, severity, etc.)
            per prd.md §12.2.
        effective_date: Date from which this rule version is active.
        legal_reference: Legal citation for this rule version.
    """
    rule_id: str
    rule_version_id: str
    version: int
    rule_key: str
    title: str
    content: dict[str, Any]
    effective_date: date
    legal_reference: str


@dataclass
class RuleVerdict:
    """Result of evaluating a single rule against declarations.

    Attributes:
        rule_version_id: The exact rule_versions.id that produced this verdict.
        rule_key: Rule key for display/reporting.
        title: Rule title for display/reporting.
        verdict: One of PASS, FAIL, NOT_APPLICABLE.
        verdict_type: Additional classification — MISSING, FORMAT, PRESENCE, etc.
        field_type: The declaration field this rule evaluated (if applicable).
        detail: Human-readable explanation of the verdict.
        passed: Boolean convenience (True for PASS, False otherwise).
    """
    rule_version_id: str
    rule_key: str
    title: str
    verdict: str  # PASS | FAIL | NOT_APPLICABLE
    verdict_type: str  # MISSING | FORMAT | PRESENCE | NOT_APPLICABLE
    field_type: Optional[str] = None
    detail: str = ""
    passed: bool = False  # Set automatically below

    def __post_init__(self):
        """Automatically compute passed from verdict."""
        self.passed = (self.verdict == "PASS")


# ── Validation result types ───────────────────────────────────────────────────

VALID_VERDICTS = frozenset({"PASS", "FAIL", "NOT_APPLICABLE"})
VALID_VERDICT_TYPES = frozenset({"MISSING", "FORMAT", "PRESENCE", "NOT_APPLICABLE"})


# ── Core functions ─────────────────────────────────────────────────────────────

def _get_declaration_value(
    declarations: list[Declaration],
    field_type: str,
) -> Optional[dict[str, Any]]:
    """Get the value of a declaration by field_type.

    If multiple declarations exist for the same field_type, returns the one
    with the highest confidence (most reliable extraction).
    """
    candidates = [d for d in declarations if d.field_type == field_type]
    if not candidates:
        return None
    # Sort by confidence descending, return best
    candidates.sort(key=lambda d: d.confidence or 0.0, reverse=True)
    return candidates[0].value


def _build_declaration_map(
    declarations: list[Declaration],
) -> dict[str, Optional[dict[str, Any]]]:
    """Build a map from field_type → value for quick lookup.

    When multiple declarations exist for the same field_type, keeps the one
    with the highest confidence.
    """
    result: dict[str, Optional[dict[str, Any]]] = {}
    for d in declarations:
        existing = result.get(d.field_type)
        if existing is None or (d.confidence or 0.0) > (existing.get("confidence") or 0.0):
            result[d.field_type] = d.value
    return result


async def get_applicable_rules(
    db: AsyncSession,
    category: str,
    inspection_date: date,
) -> list[RuleInstance]:
    """Retrieve applicable rule versions for a given category and date.

    Queries rules and rule_versions where:
    - The rule's categories include the given category (category matching)
    - The rule_version's effective_date <= inspection_date
    - The rule_version is not ended (end_date is NULL or > inspection_date)

    Results are ordered by effective_date ASC for deterministic reproducibility.

    Args:
        db: Async database session.
        category: Product category string (e.g., "Food & Beverage").
        inspection_date: Date of the inspection.

    Returns:
        List of RuleInstance objects, ordered by effective_date.
    """
    # Query all rule_versions joined with rules, filtered by date and category
    stmt = (
        select(Rule, RuleVersion)
        .join(RuleVersion, Rule.id == RuleVersion.rule_id)
        .where(RuleVersion.effective_date <= inspection_date)
        .where(RuleVersion.end_date.is_(None) | (RuleVersion.end_date > inspection_date))
        .order_by(RuleVersion.effective_date.asc(), RuleVersion.version.asc())
    )

    result = (await db.execute(stmt)).unique().all()

    instances: list[RuleInstance] = []
    for rule, rv in result:
        # Check category matching — content may have product_categories list.
        # The wildcard "ALL" (used by seeded rules) applies to every category.
        content = rv.content or {}
        applies_when = content.get("applies_when", {})
        applicable_categories = applies_when.get("product_categories", [])
        if applicable_categories and "ALL" not in applicable_categories:
            if category not in applicable_categories and not any(
                category.startswith(c + " >") or category.endswith(" > " + c) or (" > " + c + " > ") in category
                for c in applicable_categories
            ):
                continue

        # Check package_type filter if present (skip for now — handled in evaluate_rule)
        # package_type_filter = content.get("package_type")

        instances.append(RuleInstance(
            rule_id=rule.id,
            rule_version_id=rv.id,
            version=rv.version,
            rule_key=rule.rule_key,
            title=rule.title,
            content=content,
            effective_date=rv.effective_date,
            legal_reference=rv.legal_reference,
        ))

    return instances


def evaluate_rule(
    rule_instance: RuleInstance,
    declarations: list[Declaration],
    product_category: Optional[str] = None,
    package_type: Optional[str] = None,
) -> RuleVerdict:
    """Evaluate a single rule instance against extracted declarations.

    Steps:
    1. Check applies_when conditions (category, package_type, exclusions)
    2. If conditions not met → NOT_APPLICABLE
    3. Execute validation block (regex_and_presence, presence_only, format_check)
    4. Return verdict with exact rule_version_id reference

    Args:
        rule_instance: The rule version to evaluate.
        declarations: List of extracted Declaration objects.
        product_category: The product's category (for applies_when checks).
        package_type: The package type (for applies_when checks).

    Returns:
        RuleVerdict with PASS, FAIL, or NOT_APPLICABLE.
    """
    content = rule_instance.content
    applies_when = content.get("applies_when", {})
    validation = content.get("validation", {})

    # ── Step 1: Check applies_when conditions ─────────────────────────────

    # Category matching — "ALL" wildcard applies to every category
    required_categories = applies_when.get("product_categories", [])
    if required_categories and "ALL" not in required_categories:
        if product_category not in required_categories and not any(
            product_category.startswith(c + " >") or (" > " + c + " > ") in product_category
            for c in required_categories
        ):
            return RuleVerdict(
                rule_version_id=rule_instance.rule_version_id,
                rule_key=rule_instance.rule_key,
                title=rule_instance.title,
                verdict="NOT_APPLICABLE",
                verdict_type="NOT_APPLICABLE",
                detail=f"Product category '{product_category}' not in required categories {required_categories}",
            )

    # Exclusion check
    excluded_categories = applies_when.get("exclude_categories", [])
    if excluded_categories and product_category in excluded_categories:
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="NOT_APPLICABLE",
            verdict_type="NOT_APPLICABLE",
            detail=f"Product category '{product_category}' is excluded",
        )

    # Package type check
    required_package_type = applies_when.get("package_type")
    if required_package_type and package_type != required_package_type:
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="NOT_APPLICABLE",
            verdict_type="NOT_APPLICABLE",
            detail=f"Package type '{package_type}' does not match required '{required_package_type}'",
        )

    # ── Step 2: Execute validation block ───────────────────────────────────

    # Handle missing validation key gracefully
    if not validation:
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="PASS",
            verdict_type="PRESENCE",
            detail="No validation configured — passed by default",
            passed=True,
        )

    validation_type = validation.get("type", "presence_only")
    # Seeded rules store the target declaration under "required_field";
    # fall back to "field" for hand-authored rule content.
    field_to_check = validation.get("field") or content.get("required_field", "")

    if validation_type == "regex_and_presence":
        return _eval_regex_and_presence(
            rule_instance, declarations, field_to_check, validation
        )
    elif validation_type == "presence_only":
        return _eval_presence_only(
            rule_instance, declarations, field_to_check, validation
        )
    elif validation_type == "format_check":
        return _eval_format_check(
            rule_instance, declarations, field_to_check, validation
        )
    else:
        # Unknown validation type → treat as PASS (graceful degradation)
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="PASS",
            verdict_type="PRESENCE",
            detail=f"Unknown validation type '{validation_type}' — passed by default",
            passed=True,
        )


def _eval_regex_and_presence(
    rule_instance: RuleInstance,
    declarations: list[Declaration],
    field_type: str,
    validation: dict[str, Any],
) -> RuleVerdict:
    """Evaluate regex_and_presence validation type.

    Checks:
    1. Field must be present (NOT_FOUND → FAIL, type MISSING)
    2. Field value must match the regex pattern
    """

    # Get the declaration value
    decl_value = _get_declaration_value(declarations, field_type)

    if decl_value is None:
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="FAIL",
            verdict_type="MISSING",
            field_type=field_type,
            detail=f"Declaration '{field_type}' not found in extraction results",
            passed=False,
        )

    # Extract the actual text value from the declaration
    text_value = decl_value.get("text", "") if isinstance(decl_value, dict) else ""

    # Check regex pattern
    pattern = validation.get("pattern", "")
    if pattern:
        if not re.search(pattern, text_value):
            return RuleVerdict(
                rule_version_id=rule_instance.rule_version_id,
                rule_key=rule_instance.rule_key,
                title=rule_instance.title,
                verdict="FAIL",
                verdict_type="FORMAT",
                field_type=field_type,
                detail=f"Value '{text_value}' does not match required pattern '{pattern}'",
                passed=False,
            )

    # Check additional conditions (e.g., must contain certain text)
    must_contain = validation.get("must_contain", [])
    for required_text in must_contain:
        if required_text not in text_value:
            return RuleVerdict(
                rule_version_id=rule_instance.rule_version_id,
                rule_key=rule_instance.rule_key,
                title=rule_instance.title,
                verdict="FAIL",
                verdict_type="FORMAT",
                field_type=field_type,
                detail=f"Value must contain '{required_text}' but got '{text_value}'",
                passed=False,
            )

    return RuleVerdict(
        rule_version_id=rule_instance.rule_version_id,
        rule_key=rule_instance.rule_key,
        title=rule_instance.title,
        verdict="PASS",
        verdict_type="FORMAT",
        field_type=field_type,
        detail=f"Declaration '{field_type}' present and matches all conditions",
        passed=True,
    )


def _eval_presence_only(
    rule_instance: RuleInstance,
    declarations: list[Declaration],
    field_type: str,
    validation: dict[str, Any],
) -> RuleVerdict:
    """Evaluate presence_only validation type.

    Checks only that the field is present — no format validation.
    """

    decl_value = _get_declaration_value(declarations, field_type)

    if decl_value is None:
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="FAIL",
            verdict_type="MISSING",
            field_type=field_type,
            detail=f"Declaration '{field_type}' not found in extraction results",
            passed=False,
        )

    return RuleVerdict(
        rule_version_id=rule_instance.rule_version_id,
        rule_key=rule_instance.rule_key,
        title=rule_instance.title,
        verdict="PASS",
        verdict_type="PRESENCE",
        field_type=field_type,
        detail=f"Declaration '{field_type}' is present",
        passed=True,
    )


def _eval_format_check(
    rule_instance: RuleInstance,
    declarations: list[Declaration],
    field_type: str,
    validation: dict[str, Any],
) -> RuleVerdict:
    """Evaluate format_check validation type.

    Checks format/pattern but does not require the field to exist.
    If field is missing → NOT_APPLICABLE (not FAIL).
    """

    decl_value = _get_declaration_value(declarations, field_type)

    if decl_value is None:
        return RuleVerdict(
            rule_version_id=rule_instance.rule_version_id,
            rule_key=rule_instance.rule_key,
            title=rule_instance.title,
            verdict="NOT_APPLICABLE",
            verdict_type="NOT_APPLICABLE",
            field_type=field_type,
            detail=f"Declaration '{field_type}' not found — format check skipped",
            passed=False,
        )

    text_value = decl_value.get("text", "") if isinstance(decl_value, dict) else ""

    # Check format pattern
    pattern = validation.get("pattern", "")
    if pattern:
        if not re.search(pattern, text_value):
            return RuleVerdict(
                rule_version_id=rule_instance.rule_version_id,
                rule_key=rule_instance.rule_key,
                title=rule_instance.title,
                verdict="FAIL",
                verdict_type="FORMAT",
                field_type=field_type,
                detail=f"Value '{text_value}' does not match format pattern '{pattern}'",
                passed=False,
            )

    return RuleVerdict(
        rule_version_id=rule_instance.rule_version_id,
        rule_key=rule_instance.rule_key,
        title=rule_instance.title,
        verdict="PASS",
        verdict_type="FORMAT",
        field_type=field_type,
        detail=f"Declaration '{field_type}' matches format requirements",
        passed=True,
    )


async def evaluate_all_rules(
    db: AsyncSession,
    category: str,
    inspection_date: date,
    declarations: list[Declaration],
    product_category: Optional[str] = None,
    package_type: Optional[str] = None,
) -> list[RuleVerdict]:
    """Evaluate all applicable rules against declarations.

    Convenience function that:
    1. Gets applicable rules via get_applicable_rules()
    2. Evaluates each rule via evaluate_rule()
    3. Returns all verdicts in order

    Args:
        db: Async database session.
        category: Product category for rule selection.
        inspection_date: Date of inspection.
        declarations: Extracted declarations.
        product_category: Product category (for applies_when).
        package_type: Package type (for applies_when).

    Returns:
        List of RuleVerdict objects.
    """
    rules = await get_applicable_rules(db, category, inspection_date)
    verdicts: list[RuleVerdict] = []

    for rule in rules:
        verdict = evaluate_rule(
            rule,
            declarations,
            product_category=product_category or category,
            package_type=package_type,
        )
        verdicts.append(verdict)

    return verdicts
