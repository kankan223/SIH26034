"""Rule model per prd.md §20.1 — rules table."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Rule(UUIDPrimaryKeyMixin, Base):
    """Rules table — stable identity for each legal rule."""
    __tablename__ = "rules"

    rule_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships
    versions = relationship("RuleVersion", back_populates="rule", lazy="selectin")
