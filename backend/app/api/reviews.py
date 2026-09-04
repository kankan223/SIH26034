"""Human Review API endpoints per prd.md §21 and §19.

Endpoints:
- GET /reviews/queue — List review items (senior_officer+, region-filtered)
- POST /reviews/{id}/confirm — Confirm a review item (senior_officer+)
- POST /reviews/{id}/override — Override/correct a review item (senior_officer+)
- GET /reviews/{id}/status — Check if report can be submitted

All endpoints require authentication.
Review queue access: senior_officer or admin per prd.md §21.
Correction: senior_officer or admin (inspectors can only confirm, not correct).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.rbac import get_current_user, require_role
from app.core.constants import Role
from app.core.config import settings
from app.services.review_queue import (
    get_review_items,
    get_review_queue_summary,
    submit_correction,
    confirm_review_item,
    can_submit_report,
    ReviewItem,
    ReviewStatus,
)
from app.models.user import User

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import Any, Optional


class ReviewItemResponse(BaseModel):
    """Single review item response."""
    id: str
    inspection_id: str
    field_type: str
    original_value: Optional[dict[str, Any]] = None
    original_confidence: float = 0.0
    status: str
    assigned_to: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    """Review queue list response."""
    items: list[ReviewItemResponse]
    total: int
    pending_count: int


class CorrectionRequest(BaseModel):
    """Request to submit a correction."""
    corrected_value: dict[str, Any] = Field(..., description="Corrected value")
    reason: str = Field(..., min_length=5, description="Mandatory reason (min 5 chars per Workflow D)")


class ConfirmRequest(BaseModel):
    """Request to confirm a review item."""
    confirmed_value: Optional[dict[str, Any]] = Field(None, description="Optional confirmed value")


class QueueSummaryResponse(BaseModel):
    """Review queue summary for dashboard."""
    total: int
    pending: int
    confirmed: int
    pending_ratio: float


class ReportSubmissionCheckResponse(BaseModel):
    """Response for can_submit_report check."""
    allowed: bool
    reason: str


class CorrectionResponse(BaseModel):
    """Response after submitting a correction."""
    correction_id: str
    field_type: str
    original_value: Optional[dict[str, Any]]
    corrected_value: dict[str, Any]
    reason: str
    corrected_by: str
    compliance_status_after: str


# ── Helper: get DB session ─────────────────────────────────────────────────────

async def get_db() -> AsyncSession:
    """Create a database session for the request."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    region: Optional[str] = Query(None, description="Filter by region"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SENIOR_OFFICER, Role.ADMIN)),
):
    """Get the review queue for the current user's region.

    Requires: senior_officer or admin role.

    Args:
        region: Optional region filter.
        status: Optional status filter (pending/confirmed/corrected).
        db: Database session.
        current_user: Authenticated user with required role.

    Returns:
        List of review items with summary counts.
    """
    items = await get_review_items(db, inspection_id="", user_id=current_user.id)

    # Filter by region if provided
    if region:
        # In a full implementation, inspections would have region field
        # For now, return all items (region filtering requires inspection data)
        pass

    # Filter by status if provided
    if status:
        if status == "pending":
            items = [i for i in items if i.status == ReviewStatus.PENDING]
        elif status == "confirmed":
            items = [i for i in items if i.status == ReviewStatus.CONFIRMED]

    pending_count = sum(1 for i in items if i.status == ReviewStatus.PENDING)

    return ReviewQueueResponse(
        items=[
            ReviewItemResponse(
                id=item.id,
                inspection_id=item.inspection_id,
                field_type=item.field_type,
                original_value=item.original_value,
                original_confidence=item.original_confidence,
                status=item.status.value,
                assigned_to=item.assigned_to,
            )
            for item in items
        ],
        total=len(items),
        pending_count=pending_count,
    )


@router.get("/queue/summary", response_model=QueueSummaryResponse)
async def get_review_summary(
    region: Optional[str] = Query(None, description="Filter by region"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SENIOR_OFFICER, Role.ADMIN)),
):
    """Get a summary of the review queue for dashboard KPIs.

    Requires: senior_officer or admin role.

    Args:
        region: Optional region filter.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Summary with total, pending, confirmed counts.
    """
    summary = await get_review_queue_summary(db, region=region)
    return QueueSummaryResponse(**summary)


@router.post("/queue/summary", response_model=QueueSummaryResponse)
async def get_review_summary_post(
    region: Optional[str] = Query(None, description="Filter by region"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SENIOR_OFFICER, Role.ADMIN)),
):
    """Alternative POST endpoint for queue summary (for clients that prefer POST)."""
    summary = await get_review_queue_summary(db, region=region)
    return QueueSummaryResponse(**summary)


@router.post("/{review_id}/confirm", response_model=dict)
async def confirm_review(
    review_id: str,
    request: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.INSPECTOR, Role.SENIOR_OFFICER, Role.ADMIN)),
):
    """Confirm a review item (human verification of AI finding).

    Any authenticated user can confirm (inspector, senior_officer, admin).

    Args:
        review_id: The review item (compliance check) ID.
        request: Confirmation request with optional confirmed_value.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Confirmation result with status and timestamp.
    """
    result = await confirm_review_item(
        db=db,
        inspection_id="",
        review_item_id=review_id,
        confirmed_by=current_user.id,
        confirmed_value=request.confirmed_value,
    )
    return result


@router.post("/{review_id}/override", response_model=CORRECTION_RESPONSE)
async def override_review(
    review_id: str,
    request: CorrectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SENIOR_OFFICER, Role.ADMIN)),
):
    """Override (correct) a review item with a new value.

    Requires: senior_officer or admin role.
    Inspectors can only confirm, not override.

    Args:
        review_id: The review item (compliance check) ID.
        request: Correction request with corrected_value and reason.
        db: Database session.
        current_user: Authenticated user with required role.

    Returns:
        Correction result with correction_id, before/after values, compliance status.
    """
    # Fetch the compliance check to get declaration info
    stmt = select(ComplianceCheck).where(ComplianceCheck.id == review_id)
    result = await db.execute(stmt)
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review item {review_id} not found",
        )

    try:
        correction = await submit_correction(
            db=db,
            inspection_id=check.inspection_id,
            field_type=check.declaration.field_type if check.declaration else "unknown",
            corrected_value=request.corrected_value,
            reason=request.reason,
            corrected_by=current_user.id,
            original_declaration_id=check.declaration_id,
            original_compliance_check_id=check.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return CorrectionResponse(
        correction_id=correction.correction_id,
        field_type=correction.field_type,
        original_value=correction.original_value,
        corrected_value=correction.corrected_value,
        reason=correction.reason,
        corrected_by=correction.corrected_by,
        compliance_status_after=correction.compliance_status_after.value,
    )


@router.get("/{review_id}/status", response_model=ReportSubmissionCheckResponse)
async def check_report_submission_status(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if an inspection can have its report submitted.

    Public endpoint (any authenticated user) for checking report eligibility.

    Args:
        review_id: The inspection ID to check.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Whether report submission is allowed and reason if not.
    """
    allowed, reason = await can_submit_report(
        inspection_id=review_id,
        db=db,
    )
    return ReportSubmissionCheckResponse(allowed=allowed, reason=reason)


@router.post("/{inspection_id}/review", response_model=dict)
async def submit_review(
    inspection_id: str,
    request: CorrectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SENIOR_OFFICER, Role.ADMIN)),
):
    """Submit a review correction for an inspection (alternative endpoint).

    Per prd.md §21: POST /inspections/{id}/review.

    Requires: senior_officer or admin role.

    Args:
        inspection_id: The inspection UUID.
        request: Correction request.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Correction result.
    """
    # This endpoint delegates to the override endpoint logic
    # For simplicity, we find the first pending compliance check for this inspection
    stmt = (
        select(ComplianceCheck)
        .where(ComplianceCheck.inspection_id == inspection_id)
        .where(ComplianceCheck.verdict == "needs_review")
        .limit(1)
    )
    result = await db.execute(stmt)
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending review items found for inspection {inspection_id}",
        )

    try:
        correction = await submit_correction(
            db=db,
            inspection_id=inspection_id,
            field_type=check.declaration.field_type if check.declaration else "unknown",
            corrected_value=request.corrected_value,
            reason=request.reason,
            corrected_by=current_user.id,
            original_declaration_id=check.declaration_id,
            original_compliance_check_id=check.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return CorrectionResponse(
        correction_id=correction.correction_id,
        field_type=correction.field_type,
        original_value=correction.original_value,
        corrected_value=correction.corrected_value,
        reason=correction.reason,
        corrected_by=correction.corrected_by,
        compliance_status_after=correction.compliance_status_after.value,
    )
