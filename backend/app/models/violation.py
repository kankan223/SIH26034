"""Violation model per prd.md §20.1 — violations table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Violation(UUIDPrimaryKeyMixin, Base):
    """Violations table — individual rule violations per inspection."""
    __tablename__ = "violations"

    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    compliance_check_id: Mapped[str] = mapped_column(ForeignKey("compliance_checks.id"), nullable=False)
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)  # critical|major|minor
    issue_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    expected_condition: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="violations", lazy="selectin")
    compliance_check = relationship("ComplianceCheck", back_populates="violations", lazy="selectin")
    evidence = relationship("Evidence", back_populates="violation", lazy="selectin")
