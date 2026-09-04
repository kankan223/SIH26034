"""Inspection model per prd.md §20.1 — inspections table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Inspection(UUIDPrimaryKeyMixin, Base):
    """Inspections table — core workflow entity per prd.md §5."""
    __tablename__ = "inspections"

    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), nullable=True)  # FK to products
    inspector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="physical")
    overall_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    product = relationship("Product", back_populates="inspections", lazy="selectin")
    inspector = relationship("User", back_populates="inspections", lazy="selectin")
    images = relationship("Image", back_populates="inspection", lazy="selectin")
    declarations = relationship("Declaration", back_populates="inspection", lazy="selectin")
    compliance_checks = relationship("ComplianceCheck", back_populates="inspection", lazy="selectin")
    violations = relationship("Violation", back_populates="inspection", lazy="selectin")
    report = relationship("Report", back_populates="inspection", uselist=False, lazy="selectin")
