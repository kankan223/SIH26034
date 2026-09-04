"""Rule management API endpoints.

Per prd.md §21: admin-only endpoints for rule CRUD and version management.
Per prd.md §12.4: append-only versioning — historical versions are never mutated.
Per prd.md §12.6: legal_reference required before publish.

Endpoints:
- GET /rules — List rules (admin/senior_officer)
- POST /rules — Create a new rule (admin only)
- GET /rules/{rule_id} — Get rule detail with versions (admin/senior_officer)
- POST /rules/{rule_id}/versions — Add a new version (admin only)
- POST /rules/{rule_id}/versions/{version_id}/publish — Publish a version (admin only)
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_role
from app.core.constants import Role
from app.db.db_session import get_db
from app.models.rule import Rule
from app.models.rule_version import RuleVersion
from app.schemas.rule import (
    RuleCreateRequest,
    RuleDetailResponse,
    RuleListQueryParams,
    RuleListResponse,
    RuleVersionCreateRequest,
    RuleVersionPublishRequest,
    RuleVersionResponse,
)

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


# ── Helper: get current published version ─────────────────────────────────────

async def _get_current_published_version(db: AsyncSession, rule: Rule) -> Optional[RuleVersion]:
    """Get the currently published (active) version of a rule."""
    stmt = (
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule.id)
        .order_by(RuleVersion.effective_date.desc())
    )
    result = await db.execute(stmt)
    versions = list(result.scalars().all())

    for v in versions:
        if v.published_at is not None and (v.end_date is None or v.end_date >= date.today()):
            return v
    return None


# ── GET /rules — List rules ────────────────────────────────────────────────────

@router.get("/", response_model=RuleListResponse)
async def list_rules(
    category: Optional[str] = Query(None, description="Filter by product category"),
    effective_after: Optional[date] = Query(None, description="Only rules effective after this date"),
    effective_before: Optional[date] = Query(None, description="Only rules effective before this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(Role.ADMIN, Role.SENIOR_OFFICER)),
):
    """List all rules with optional filtering.

    Admin and senior officers can view rules.
    """
    query = select(Rule).order_by(Rule.rule_key.asc())

    if category:
        query = query.where(Rule.rule_key.ilike(f"%{category}%"))

    result = await db.execute(query)
    all_rules = list(result.scalars().all())

    # Apply date filtering and build response
    rule_summaries = []
    for rule in all_rules:
        current_version = await _get_current_published_version(db, rule)
        if current_version is None:
            continue  # Skip rules with no published version

        if effective_after and current_version.effective_date < effective_after:
            continue
        if effective_before and current_version.effective_date > effective_before:
            continue

        rule_summaries.append(RuleListResponse.RuleSummary(
            id=rule.id,
            rule_key=rule.rule_key,
            title=rule.title,
            version=current_version.version,
            latest_version_id=current_version.id,
            effective_date=current_version.effective_date,
            product_categories=current_version.content.get("product_categories", []),
            severity=current_version.content.get("severity", "major"),
        ))

    # Pagination
    total = len(rule_summaries)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = rule_summaries[start:end]

    return RuleListResponse(rules=paginated)


# ── POST /rules — Create rule ──────────────────────────────────────────────────

@router.post("/", response_model=RuleVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: RuleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """Create a new rule with an initial draft version.

    Only admins can create rules.
    The initial version is created as a draft (not published).
    """
    # Check for duplicate rule_key
    existing = await db.execute(
        select(Rule).where(Rule.rule_key == request.rule_key)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule with key '{request.rule_key}' already exists",
        )

    # Create the rule
    rule = Rule(
        rule_key=request.rule_key,
        title=request.title,
        description=request.description,
    )
    db.add(rule)
    await db.flush()  # Get the rule ID

    # Create initial version with empty content (will be filled later)
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        content={
            "applies_when": {
                "product_categories": request.product_categories,
                "package_type": request.package_type,
            },
            "validation": {},
            "severity": request.severity,
        },
        legal_reference="",  # Draft — no legal reference yet
        effective_date=date.today(),
    )
    db.add(version)

    await db.commit()
    await db.refresh(rule)
    await db.refresh(version)

    return RuleVersionResponse.VersionCreated(
        id=version.id,
        version=version.version,
        content=version.content,
        legal_reference=version.legal_reference,
        effective_date=version.effective_date,
        message=f"Rule '{rule.rule_key}' created with draft version {version.version}. "
                f"Add legal_reference and publish to activate.",
    )


# ── GET /rules/{rule_id} — Get rule detail ─────────────────────────────────────

@router.get("/{rule_id}", response_model=RuleDetailResponse)
async def get_rule_detail(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(Role.ADMIN, Role.SENIOR_OFFICER)),
):
    """Get full rule detail including all versions.

    Admin and senior officers can view rule details.
    """
    rule = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule_obj = rule.scalar_one_or_none()

    if rule_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' not found",
        )

    # Get all versions
    versions_result = await db.execute(
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version.asc())
    )
    versions = list(versions_result.scalars().all())

    version_infos = []
    current_version_id = None
    current_effective_date = None

    for v in versions:
        is_published = v.published_at is not None
        version_infos.append(RuleDetailResponse.VersionInfo(
            id=v.id,
            version=v.version,
            content=v.content,
            legal_reference=v.legal_reference,
            effective_date=v.effective_date,
            end_date=v.end_date,
            published_by=v.published_by,
            published_at=v.published_at.date() if v.published_at else None,
            is_published=is_published,
        ))
        if is_published and current_effective_date is None:
            current_version_id = v.id
            current_effective_date = v.effective_date

    # Also check for a currently active published version
    if current_version_id is None:
        for v in versions:
            if v.published_at is not None and (v.end_date is None or v.end_date >= date.today()):
                current_version_id = v.id
                current_effective_date = v.effective_date
                break

    return RuleDetailResponse(
        id=rule_obj.id,
        rule_key=rule_obj.rule_key,
        title=rule_obj.title,
        description=rule_obj.description,
        versions=version_infos,
        current_version_id=current_version_id,
        current_effective_date=current_effective_date,
    )


# ── POST /rules/{rule_id}/versions — Add version ───────────────────────────────

@router.post("/{rule_id}/versions", response_model=RuleVersionResponse)
async def create_rule_version(
    rule_id: str,
    request: RuleVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """Create a new version of an existing rule.

    Only admins can create versions.
    The rule's previous versions are never modified (append-only per §12.4).
    """
    # Verify rule exists
    rule_result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = rule_result.scalar_one_or_none()

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' not found",
        )

    # Get the latest version number
    latest_result = await db.execute(
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version.desc())
    )
    latest = latest_result.scalar_one_or_none()
    new_version_num = (latest.version + 1) if latest else 1

    # Validate: legal_reference must be non-empty (per §12.6)
    if not request.legal_reference or not request.legal_reference.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="legal_reference is required and must be non-empty per prd.md §12.6",
        )

    # Validate: check for overlapping effective_date with existing published versions
    existing_result = await db.execute(
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule_id)
        .where(RuleVersion.published_at.isnot(None))
    )
    existing_published = list(existing_result.scalars().all())

    new_start = request.effective_date
    new_end = request.end_date or date(9999, 12, 31)

    for existing in existing_published:
        ex_start = existing.effective_date
        ex_end = existing.end_date or date(9999, 12, 31)
        # Check overlap
        if new_start <= ex_end and new_end >= ex_start:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Effective date range ({new_start} to {new_end}) overlaps with "
                       f"existing published version {existing.version} "
                       f"({ex_start} to {ex_end}). Per prd.md §12.4, overlapping dates are not allowed.",
            )

    # Create the new version
    version = RuleVersion(
        rule_id=rule_id,
        version=new_version_num,
        content=request.content,
        legal_reference=request.legal_reference,
        effective_date=request.effective_date,
        end_date=request.end_date,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    return RuleVersionResponse.VersionCreated(
        id=version.id,
        version=version.version,
        content=version.content,
        legal_reference=version.legal_reference,
        effective_date=version.effective_date,
        message=f"Version {new_version_num} created for rule '{rule.rule_key}'. "
                f"Publish to make effective.",
    )


# ── POST /rules/{rule_id}/versions/{version_id}/publish — Publish version ─────

@router.post(
    "/{rule_id}/versions/{version_id}/publish",
    response_model=RulePublishResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_rule_version(
    rule_id: str,
    version_id: str,
    request: RuleVersionPublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(Role.ADMIN)),
):
    """Publish a rule version, making it effective.

    Only admins can publish rules.
    Per prd.md §12.6: the version must have a non-empty legal_reference.
    Per prd.md §12.4: publishing sets published_at; historical versions are never mutated.
    An audit log entry is created for this action.
    """
    # Verify rule exists
    rule_result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = rule_result.scalar_one_or_none()

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' not found",
        )

    # Verify version exists and belongs to this rule
    version_result = await db.execute(
        select(RuleVersion).where(
            RuleVersion.id == version_id,
            RuleVersion.rule_id == rule_id,
        )
    )
    version = version_result.scalar_one_or_none()

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version_id}' not found for rule '{rule_id}'",
        )

    # Validate: legal_reference must be non-empty (per §12.6)
    if not version.legal_reference or not version.legal_reference.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish version {version.version}: legal_reference is empty. "
                   f"Add a legal_reference before publishing per prd.md §12.6.",
        )

    # Validate: version must not already be published
    if version.published_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version {version.version} is already published at {version.published_at}",
        )

    # Publish the version
    now = datetime.now(timezone.utc)
    version.published_by = request.published_by
    version.published_at = now

    await db.commit()
    await db.refresh(version)

    # Log audit entry (import here to avoid circular imports)
    from app.services.audit_service import log_action

    await log_action(
        db=db,
        actor_id=request.published_by,
        action="publish_rule_version",
        entity_type="rule_version",
        entity_id=version.id,
        before_value=None,
        after_value={
            "rule_key": rule.rule_key,
            "version": version.version,
            "legal_reference": version.legal_reference,
            "effective_date": str(version.effective_date),
        },
    )

    return RulePublishResponse(
        version=RulePublishResponse.PublishedVersion(
            id=version.id,
            version=version.version,
            effective_date=version.effective_date,
            published_at=now.date(),
            published_by=request.published_by,
        ),
        message=f"Rule '{rule.rule_key}' version {version.version} published successfully. "
                f"Effective from {version.effective_date}.",
    )
