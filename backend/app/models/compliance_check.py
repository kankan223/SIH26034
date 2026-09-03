"""Compliance Check model per prd.md §20.1 — compliance_checks table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class ComplianceCheck(UUIDPrimaryKeyMixin, Base):
    """Compliance Checks table — per-rule evaluation results."""
    __tablename__ = "compliance_checks"

    inspection_id: Mapped[str] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    rule_version_id: Mapped[str] = mapped_column(ForeignKey("rule_versions.id"), nullable=False)
    declaration_id: Mapped[Optional[str]] = mapped_column(ForeignKey("declarations.id"), nullable=True)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)  # pass|fail|needs_review|not_applicable
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="compliance_checks", lazy="selectin")
    rule_version = relationship("RuleVersion", back_populates="compliance_checks", lazy="selectin")
    declaration = relationship("Declaration", back_populates="compliance_checks", lazy="selectin")
    violations = relationship("Violation", back_populates="compliance_check", lazy="selectin")
    corrections = relationship("Correction", back_populates="compliance_check", lazy="selectin")
