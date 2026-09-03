"""Correction model per prd.md §20.1 — corrections table."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Correction(UUIDPrimaryKeyMixin, Base):
    """Corrections table — human corrections to AI findings per Workflow D."""
    __tablename__ = "corrections"

    declaration_id: Mapped[Optional[str]] = mapped_column(ForeignKey("declarations.id"), nullable=True)
    compliance_check_id: Mapped[Optional[str]] = mapped_column(ForeignKey("compliance_checks.id"), nullable=True)
    corrected_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    original_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    corrected_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # required, non-empty per Workflow D
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    declaration = relationship("Declaration", back_populates="corrections", lazy="selectin")
    compliance_check = relationship("ComplianceCheck", back_populates="corrections", lazy="selectin")
    corrector = relationship("User", lazy="selectin")
