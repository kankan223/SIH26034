"""Category model per prd.md §20.1 — categories table."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, Base):
    """Categories table — self-referential taxonomy tree per prd.md §13.1."""
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)

    # Self-referential relationship
    children = relationship("Category", back_populates="parent", lazy="selectin")
    parent = relationship("Category", back_populates="children", remote_side="Category.id", lazy="selectin")
    products = relationship("Product", back_populates="category", lazy="selectin")
