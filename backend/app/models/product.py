"""Product model per prd.md §20.1 — products table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, Base):
    """Products table — stores product metadata linked to inspections."""
    __tablename__ = "products"

    barcode: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    manufacturer_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    previous_inspection_id: Mapped[Optional[str]] = mapped_column(nullable=True)  # FK added after Inspection model
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    category = relationship("Category", back_populates="products", lazy="selectin")
    inspections = relationship("Inspection", back_populates="product", lazy="selectin")
