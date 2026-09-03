"""Report model per prd.md §20.1 — reports table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Report(UUIDPrimaryKeyMixin, Base):
    """Reports table — generated PDF reports per inspection."""
    __tablename__ = "reports"

    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    pdf_storage_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    editable_export_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    inspection = relationship("Inspection", back_populates="report", lazy="selectin")
    generator = relationship("User", lazy="selectin")
