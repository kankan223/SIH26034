"""Rule Version model per prd.md §20.1 — rule_versions table."""

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class RuleVersion(UUIDPrimaryKeyMixin, Base):
    """Rule Versions table — versioned rule content per prd.md §12.4."""
    __tablename__ = "rule_versions"

    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # rule schema per §12.2
    legal_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    published_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    rule = relationship("Rule", back_populates="versions", lazy="selectin")
    compliance_checks = relationship("ComplianceCheck", back_populates="rule_version", lazy="selectin")
