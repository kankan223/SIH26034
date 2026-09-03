"""OCR Result model per prd.md §20.1 — ocr_results table."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class OCRResult(UUIDPrimaryKeyMixin, Base):
    """OCR Results table — stores PaddleOCR output per image."""
    __tablename__ = "ocr_results"

    image_id: Mapped[str] = mapped_column(ForeignKey("images.id"), nullable=False)
    raw_text: Mapped[str] = mapped_column(String(5000), nullable=False)
    bbox: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # [x1,y1,x2,y2]
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # en, hi
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    image = relationship("Image", back_populates="ocr_results", lazy="selectin")
    declaration = relationship("Declaration", back_populates="source_ocr_result", uselist=False, lazy="selectin")
