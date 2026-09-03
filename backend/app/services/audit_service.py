"""Audit logging service per prd.md §20.1.

Append-only logging of every state-changing action.
No UPDATE/DELETE grants for the application DB role.
"""

import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


async def log_action(
    actor_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: str,
    before_value: Optional[dict[str, Any]] = None,
    after_value: Optional[dict[str, Any]] = None,
    reason: Optional[str] = None,
) -> None:
    """Write an audit log entry.

    This is an append-only operation — no UPDATE/DELETE on audit_logs table.

    Args:
        actor_id: User ID performing the action (None for system actions)
        action: Action type (e.g., "create", "update", "delete", "review")
        entity_type: Entity type (e.g., "inspection", "rule", "correction")
        entity_id: Entity ID
        before_value: Previous state (for updates)
        after_value: New state (for creates/updates)
        reason: Reason for the action (required for corrections per Workflow D)
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    log_id = str(uuid.uuid4())

    async with async_session() as session:
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
                "before_value": before_value,
                "after_value": after_value,
                "reason": reason,
            },
        )
        await session.commit()

    await engine.dispose()
