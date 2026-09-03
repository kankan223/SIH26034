"""Evidence model per prd.md §20.1 — evidence table."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Evidence(UUIDPrimaryKeyMixin, Base):
    """Evidence table — bbox-grounded evidence per violation per prd.md §18."""
    __tablename__ = "evidence"

    violation_id: Mapped[str] = mapped_column(ForeignKey("violations.id"), nullable=False)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id"), nullable=False)
    bbox: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # [x1,y1,x2,y2]
    crop_storage_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    violation = relationship("Violation", back_populates="evidence", lazy="selectin")
    image = relationship("Image", back_populates="evidence", lazy="selectin")
