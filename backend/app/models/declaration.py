"""Declaration model per prd.md §20.1 — declarations table."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Declaration(UUIDPrimaryKeyMixin, Base):
    """Declarations table — extracted mandatory declaration fields per inspection."""
    __tablename__ = "declarations"

    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    field_type: Mapped[str] = mapped_column(String(100), nullable=False)  # enum: manufacturer_name, mrp, etc.
    value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    bbox: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # [x1,y1,x2,y2]
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    source_ocr_result_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ocr_results.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="declarations", lazy="selectin")
    source_ocr_result = relationship("OCRResult", back_populates="declaration", lazy="selectin")
    compliance_checks = relationship("ComplianceCheck", back_populates="declaration", lazy="selectin")
    corrections = relationship("Correction", back_populates="declaration", lazy="selectin")
