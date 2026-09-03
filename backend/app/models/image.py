"""Image model per prd.md §20.1 — images table."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Image(UUIDPrimaryKeyMixin, Base):
    """Images table — stores uploaded package/label images per inspection."""
    __tablename__ = "images"

    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    storage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_issues: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="images", lazy="selectin")
    ocr_results = relationship("OCRResult", back_populates="image", lazy="selectin")
    evidence = relationship("Evidence", back_populates="image", lazy="selectin")
