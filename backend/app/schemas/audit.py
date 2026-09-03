"""Pydantic schemas for audit log endpoints per prd.md §20.1."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    """Audit log creation request (internal use only, not exposed via API)."""
    actor_id: Optional[str] = Field(None, description="User ID performing the action (None for system)")
    action: str = Field(..., description="Action type: create, update, delete, review, upload_image, status_change")
    entity_type: str = Field(..., description="Entity type: inspection, image, rule, correction, report")
    entity_id: str = Field(..., description="Entity UUID")
    before_value: Optional[dict[str, Any]] = Field(None, description="Previous state (for updates)")
    after_value: Optional[dict[str, Any]] = Field(None, description="New state (for creates/updates)")
    reason: Optional[str] = Field(None, description="Reason for the action (required for corrections)")


class AuditLogResponse(BaseModel):
    """Audit log response body per prd.md §20.1."""
    id: str
    actor_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    before_value: Optional[dict[str, Any]] = None
    after_value: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""
    items: list[AuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 50


class AuditLogFilterParams(BaseModel):
    """Query parameters for filtering audit logs."""
    action: Optional[str] = Field(None, description="Filter by action type")
    resource_type: Optional[str] = Field(None, description="Filter by resource type")
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class AuditLogEntityHistoryResponse(BaseModel):
    """Response for entity audit history."""
    entity_type: str
    entity_id: str
    history: list[AuditLogResponse]
    total: int
