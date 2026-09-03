"""Pydantic schemas for inspection endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateInspectionRequest(BaseModel):
    """Create inspection request body per prd.md §21."""
    product_id: Optional[str] = None
    location: Optional[str] = None
    region: Optional[str] = None
    source: str = "physical"


class InspectionResponse(BaseModel):
    """Inspection response body."""
    id: str
    product_id: Optional[str] = None
    inspector_id: str
    status: str
    location: Optional[str] = None
    region: Optional[str] = None
    source: str
    overall_status: Optional[str] = None
    created_at: datetime
    submitted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InspectionListResponse(BaseModel):
    """Paginated inspection list."""
    items: list[InspectionResponse]
    total: int
    page: int = 1
    page_size: int = 20
