"""Audit logging service per prd.md §20.1.

Append-only logging of every state-changing action.
No UPDATE/DELETE grants for the application DB role.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


def _get_engine_and_session():
    """Create engine and session factory."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


async def log_action(
    actor_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: str,
    before_value: Optional[dict[str, Any]] = None,
    after_value: Optional[dict[str, Any]] = None,
    reason: Optional[str] = None,
) -> str:
    """Write an audit log entry (append-only).

    Args:
        actor_id: User ID performing the action (None for system actions)
        action: Action type (e.g., "create", "update", "delete", "review", "status_change")
        entity_type: Entity type (e.g., "inspection", "rule", "correction")
        entity_id: Entity ID
        before_value: Previous state (for updates)
        after_value: New state (for creates/updates)
        reason: Reason for the action (required for corrections per Workflow D)

    Returns:
        The ID of the created audit log entry.
    """
    engine, session_factory = _get_engine_and_session()
    log_id = str(uuid.uuid4())

    # Raw-SQL params: asyncpg requires jsonb values as JSON strings, not dicts
    before_json = json.dumps(before_value) if before_value is not None else None
    after_json = json.dumps(after_value) if after_value is not None else None

    try:
        async with session_factory() as session:
            await session.execute(
                text("""INSERT INTO audit_logs (id, actor_id, action, entity_type, entity_id,
                         before_value, after_value, reason)
                         VALUES (:id, :actor_id, :action, :entity_type, :entity_id,
                         :before_value, :after_value, :reason)"""),
                {
                    "id": log_id,
                    "actor_id": actor_id,
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "before_value": before_json,
                    "after_value": after_json,
                    "reason": reason,
                },
            )
            await session.commit()
    finally:
        await engine.dispose()

    return log_id


async def get_audit_logs(
    page: int = 1,
    page_size: int = 50,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> tuple[list[dict[str, Any]], int]:
    """Query audit logs with filtering and pagination.

    Returns (items, total_count).
    """
    engine, session_factory = _get_engine_and_session()

    try:
        conditions = []
        params: dict[str, Any] = {}

        if entity_type:
            conditions.append("entity_type = :entity_type")
            params["entity_type"] = entity_type
        if entity_id:
            conditions.append("entity_id = :entity_id")
            params["entity_id"] = entity_id
        if actor_id:
            conditions.append("actor_id = :actor_id")
            params["actor_id"] = actor_id
        if action:
            conditions.append("action = :action")
            params["action"] = action
        if date_from:
            conditions.append("created_at >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("created_at <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        async with session_factory() as session:
            # Count total
            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"),
                params,
            )
            total = count_result.scalar() or 0

            # Fetch page
            result = await session.execute(
                text(f"""SELECT * FROM audit_logs WHERE {where_clause}
                         ORDER BY created_at DESC LIMIT :limit OFFSET :offset"""),
                {**params, "limit": page_size, "offset": offset},
            )
            rows = result.fetchall()

        return [_row_to_dict(row) for row in rows], total
    finally:
        await engine.dispose()


async def get_audit_log_by_id(log_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single audit log entry by ID."""
    engine, session_factory = _get_engine_and_session()

    try:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM audit_logs WHERE id = :id"),
                {"id": log_id},
            )
            row = result.fetchone()
            if not row:
                return None
            return _row_to_dict(row)
    finally:
        await engine.dispose()


async def get_entity_audit_trail(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    """Get the full audit trail for a specific entity.

    Returns all audit log entries for the given entity, ordered by creation time.
    """
    engine, session_factory = _get_engine_and_session()

    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""SELECT * FROM audit_logs
                         WHERE entity_type = :entity_type AND entity_id = :entity_id
                         ORDER BY created_at ASC"""),
                {"entity_type": entity_type, "entity_id": entity_id},
            )
            rows = result.fetchall()

        return [_row_to_dict(row) for row in rows]
    finally:
        await engine.dispose()


def _row_to_dict(row) -> dict[str, Any]:
    """Convert a SQLAlchemy Row to a dict with string UUIDs."""
    if row is None:
        return {}
    d = dict(row._mapping)
    # Convert UUID fields to strings
    for key in ["id", "actor_id", "entity_id"]:
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    # Ensure datetime is properly serialized
    if "created_at" in d and d["created_at"] is not None:
        d["created_at"] = d["created_at"]
    return d
