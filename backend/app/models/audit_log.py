"""Audit Log model per prd.md §20.1 — audit_logs table (append-only)."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Audit Logs table — append-only, no UPDATE/DELETE grant per prd.md §20.1."""
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)  # nullable for system actions
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    before_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    actor = relationship("User", back_populates="audit_logs", lazy="selectin")
