"""Inspection CRUD endpoints per prd.md §21."""

import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.rbac import get_current_user, require_role
from app.schemas.inspection import (
    CreateInspectionRequest,
    ImageResponse,
    InspectionListResponse,
    InspectionResponse,
)
from app.services.audit_service import log_action
from app.services.image_processing import assess_quality

router = APIRouter(prefix="/inspections", tags=["inspections"])

# Allowed image MIME types per prd.md §10
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 15  # per prd.md §9


async def _get_db():
    """Get database session."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@router.post("", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    body: CreateInspectionRequest,
    user: dict = Depends(require_role("inspector", "senior_officer")),
) -> InspectionResponse:
    """Create a new inspection per prd.md §21.

    POST /inspections — inspector+ role required.
    Returns inspection with status "draft".
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    inspection_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text("""INSERT INTO inspections (id, inspector_id, status, location, region, source)
                     VALUES (:id, :inspector_id, 'draft', :location, :region, :source)"""),
            {
                "id": inspection_id,
                "inspector_id": user["id"],
                "location": body.location,
                "region": body.region,
                "source": body.source,
            },
        )
        await session.commit()

        # Fetch the created inspection
        result = await session.execute(
            text("SELECT * FROM inspections WHERE id = :id"),
            {"id": inspection_id},
        )
        row = result.fetchone()

    await engine.dispose()

    # Audit log
    await log_action(
        actor_id=user["id"],
        action="create",
        entity_type="inspection",
        entity_id=inspection_id,
        after_value={"status": "draft", "source": body.source},
    )

    return InspectionResponse(
        id=str(row.id),
        product_id=str(row.product_id) if row.product_id else None,
        inspector_id=str(row.inspector_id),
        status=row.status,
        location=row.location,
        region=row.region,
        source=row.source,
        overall_status=row.overall_status,
        created_at=row.created_at,
        submitted_at=row.submitted_at,
    )


@router.get("/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: str,
    user: dict = Depends(get_current_user),
) -> InspectionResponse:
    """Get inspection detail per prd.md §21.

    GET /inspections/{id} — inspector+ (owner/region) role required.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM inspections WHERE id = :id"),
            {"id": inspection_id},
        )
        row = result.fetchone()

    await engine.dispose()

    if not row:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # RBAC: inspectors can only see their own or same-region inspections
    if user["role"] == "inspector" and str(row.inspector_id) != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if user["role"] == "senior_officer" and row.region and row.region != user.get("region"):
        raise HTTPException(status_code=403, detail="Access denied — wrong region")

    return InspectionResponse(
        id=str(row.id),
        product_id=str(row.product_id) if row.product_id else None,
        inspector_id=str(row.inspector_id),
        status=row.status,
        location=row.location,
        region=row.region,
        source=row.source,
        overall_status=row.overall_status,
        created_at=row.created_at,
        submitted_at=row.submitted_at,
    )


@router.get("", response_model=InspectionListResponse)
async def list_inspections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    region: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    user: dict = Depends(get_current_user),
) -> InspectionListResponse:
    """Search/filter inspections per prd.md §21.

    GET /inspections — inspector+ (own/region), admin (all).
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    conditions = []
    params = {}

    if user["role"] == "inspector":
        conditions.append("inspector_id = :user_id")
        params["user_id"] = user["id"]
    elif user["role"] == "senior_officer":
        if region:
            conditions.append("region = :region")
            params["region"] = region
        # senior_officers see their region's inspections

    if status_filter:
        conditions.append("status = :status")
        params["status"] = status_filter

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    async with session_factory() as session:
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM inspections WHERE {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        result = await session.execute(
            text(f"""SELECT * FROM inspections WHERE {where_clause}
                     ORDER BY created_at DESC LIMIT :limit OFFSET :offset"""),
            {**params, "limit": page_size, "offset": offset},
        )
        rows = result.fetchall()

    await engine.dispose()

    items = [
        InspectionResponse(
            id=str(row.id),
            product_id=str(row.product_id) if row.product_id else None,
            inspector_id=str(row.inspector_id),
            status=row.status,
            location=row.location,
            region=row.region,
            source=row.source,
            overall_status=row.overall_status,
            created_at=row.created_at,
            submitted_at=row.submitted_at,
        )
        for row in rows
    ]

    return InspectionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{inspection_id}/images", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    inspection_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_role("inspector", "senior_officer")),
) -> ImageResponse:
    """Upload an image for an inspection per prd.md §21.

    POST /inspections/{id}/images — inspector+ role required.
    Validates MIME type and file size per prd.md §9.
    """
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # Read file content and validate size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f}MB. Maximum: {MAX_FILE_SIZE_MB}MB"
        )

    # Verify inspection exists and user has access
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT * FROM inspections WHERE id = :id"),
            {"id": inspection_id},
        )
        inspection = result.fetchone()

    if not inspection:
        await engine.dispose()
        raise HTTPException(status_code=404, detail="Inspection not found")

    # RBAC check
    if user["role"] == "inspector" and str(inspection.inspector_id) != user["id"]:
        await engine.dispose()
        raise HTTPException(status_code=403, detail="Access denied")

    # Compute content hash
    content_hash = hashlib.sha256(content).hexdigest()

    # Generate storage URL (in a real system, this would upload to MinIO)
    # For now, we store a reference URL
    storage_url = f"minio://docket-images/{inspection_id}/{content_hash[:16]}.jpg"

    # Run image quality assessment per prd.md §10.1 and FR-003
    try:
        quality_result = assess_quality(content)
        quality_score = quality_result.quality_score
        quality_issues = quality_result.quality_issues
    except Exception as e:
        # If quality assessment fails (e.g., corrupted image), flag but don't reject
        quality_score = 0.0
        quality_issues = [f"quality_assessment_failed: {str(e)}"]

    # Create image record
    image_id = str(uuid.uuid4())
    async with session_factory() as session:
        await session.execute(
            text("""INSERT INTO images (id, inspection_id, storage_url, content_hash,
                     quality_score, quality_issues)
                     VALUES (:id, :inspection_id, :storage_url, :content_hash,
                     :quality_score, :quality_issues)"""),
            {
                "id": image_id,
                "inspection_id": inspection_id,
                "storage_url": storage_url,
                "content_hash": content_hash,
                "quality_score": quality_score,
                "quality_issues": quality_issues,
            },
        )
        await session.commit()

    await engine.dispose()

    # Audit log
    await log_action(
        actor_id=user["id"],
        action="upload_image",
        entity_type="image",
        entity_id=image_id,
        after_value={
            "inspection_id": inspection_id,
            "content_hash": content_hash,
            "quality_score": quality_score,
        },
    )

    return ImageResponse(
        id=image_id,
        inspection_id=inspection_id,
        storage_url=storage_url,
        content_hash=content_hash,
        quality_score=quality_score,
        quality_issues=quality_issues,
    )
