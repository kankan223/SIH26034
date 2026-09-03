"""Inspection CRUD service per prd.md §20, §21.

Handles database operations for inspections and images.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


async def _get_session() -> AsyncSession:
    """Create and return an async database session."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    return session, engine


async def create_inspection(
    inspector_id: str,
    location: Optional[str] = None,
    region: Optional[str] = None,
    source: str = "physical",
    product_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new inspection record with status 'draft'.

    Returns the created inspection as a dict.
    """
    inspection_id = str(uuid.uuid4())
    session, engine = await _get_session()

    try:
        await session.execute(
            text("""INSERT INTO inspections (id, inspector_id, status, location, region, source, product_id)
                     VALUES (:id, :inspector_id, 'draft', :location, :region, :source, :product_id)"""),
            {
                "id": inspection_id,
                "inspector_id": inspector_id,
                "location": location,
                "region": region,
                "source": source,
                "product_id": product_id,
            },
        )
        await session.commit()

        result = await session.execute(
            text("SELECT * FROM inspections WHERE id = :id"),
            {"id": inspection_id},
        )
        row = result.fetchone()
        return _row_to_dict(row)
    finally:
        await session.close()
        await engine.dispose()


async def get_inspection(inspection_id: str) -> Optional[dict[str, Any]]:
    """Fetch an inspection by ID. Returns None if not found."""
    session, engine = await _get_session()

    try:
        result = await session.execute(
            text("SELECT * FROM inspections WHERE id = :id"),
            {"id": inspection_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        await session.close()
        await engine.dispose()


async def list_inspections(
    user_id: str,
    user_role: str,
    page: int = 1,
    page_size: int = 20,
    region: Optional[str] = None,
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    """List inspections with RBAC filtering and pagination.

    Returns (items, total_count).
    """
    session, engine = await _get_session()

    try:
        conditions = []
        params: dict[str, Any] = {}

        # RBAC: inspectors see only their own, senior_officers see by region, admins see all
        if user_role == "inspector":
            conditions.append("inspector_id = :user_id")
            params["user_id"] = user_id
        elif user_role == "senior_officer" and region:
            conditions.append("region = :region")
            params["region"] = region
        # admin: no filter — sees all

        if status_filter:
            conditions.append("status = :status")
            params["status"] = status_filter

        if date_from:
            conditions.append("created_at >= :date_from")
            params["date_from"] = date_from

        if date_to:
            conditions.append("created_at <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        # Count total
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM inspections WHERE {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        # Fetch page
        result = await session.execute(
            text(f"""SELECT * FROM inspections WHERE {where_clause}
                     ORDER BY created_at DESC LIMIT :limit OFFSET :offset"""),
            {**params, "limit": page_size, "offset": offset},
        )
        rows = result.fetchall()

        return [_row_to_dict(row) for row in rows], total
    finally:
        await session.close()
        await engine.dispose()


async def create_image(
    inspection_id: str,
    storage_url: str,
    content_hash: str,
    quality_score: Optional[float] = None,
    quality_issues: Optional[dict] = None,
) -> dict[str, Any]:
    """Create an image record linked to an inspection.

    Returns the created image as a dict.
    """
    image_id = str(uuid.uuid4())
    session, engine = await _get_session()

    try:
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

        result = await session.execute(
            text("SELECT * FROM images WHERE id = :id"),
            {"id": image_id},
        )
        row = result.fetchone()
        return _row_to_dict(row)
    finally:
        await session.close()
        await engine.dispose()


def _row_to_dict(row) -> dict[str, Any]:
    """Convert a SQLAlchemy Row to a dict with string UUIDs."""
    if row is None:
        return {}
    d = dict(row._mapping)
    for key in ["id", "inspection_id", "inspector_id", "product_id", "image_id"]:
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    return d
