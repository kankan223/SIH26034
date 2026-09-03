"""Audit log endpoints per prd.md §21 — admin-only access."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rbac import require_role
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services.audit_service import get_audit_log_by_id, get_audit_logs, get_entity_audit_trail

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    user: dict = Depends(require_role("admin")),
) -> AuditLogListResponse:
    """List audit logs with filtering per prd.md §21.

    GET /audit-logs — admin-only access per prd.md §8.5 FR-031.
    Supports filtering by entity_type, entity_id, actor_id, action, and date range.
    """
    items, total = await get_audit_logs(
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    user: dict = Depends(require_role("admin")),
) -> AuditLogResponse:
    """Get a specific audit log entry per prd.md §21.

    GET /audit-logs/{id} — admin-only access per prd.md §8.5 FR-031.
    """
    item = await get_audit_log_by_id(log_id)
    if not item:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogResponse(**item)


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogResponse])
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    user: dict = Depends(require_role("admin")),
) -> list[AuditLogResponse]:
    """Get the full audit trail for a specific entity per prd.md §21.

    GET /audit-logs/entity/{type}/{id} — admin-only access per prd.md §8.5 FR-031.
    Returns all audit log entries for the given entity, ordered by creation time.
    """
    items = await get_entity_audit_trail(entity_type, entity_id)
    return [AuditLogResponse(**item) for item in items]
