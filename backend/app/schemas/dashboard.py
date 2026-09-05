"""Pydantic schemas for dashboard API responses (prd.md §23)."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ── KPI Models ──────────────────────────────────────────────────────────────

class KPIItem(BaseModel):
    """Single KPI metric returned by GET /dashboard/kpis."""

    label: str = Field(..., description="Human-readable metric name")
    value: int | float | str = Field(..., description="Metric value")
    change_from_last_month: Optional[int] = Field(
        None, description="Percentage change vs previous month, or null"
    )


class KPIObject(BaseModel):
    """Aggregated KPI set from GET /dashboard/kpis (prd.md §23)."""

    total_inspections: int = Field(..., description="All inspections ever recorded")
    compliant_count: int = Field(..., description="Inspections with overall_status=COMPLIANT")
    non_compliant_count: int = Field(..., description="Inspections with overall_status=NON_COMPLIANT")
    flagged_for_review_count: int = Field(..., description="Inspections with overall_status=FLAGGED_FOR_REVIEW")
    pending_review_count: int = Field(..., description="Inspections with status=NEEDS_HUMAN_REVIEW")
    active_violations_count: int = Field(..., description="Violations not yet resolved")
    compliance_rate_percent: float = Field(
        ..., description="compliant / (compliant + non_compliant) * 100, rounded to 1 decimal"
    )
    total_products_categorized: int = Field(..., description="Distinct products inspected")
    top_category: Optional[str] = Field(None, description="Category with most violations, or null")


# ── Trend Models ────────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    """Single monthly data point for trend charts."""

    month: date = Field(..., description="First day of the month (YYYY-MM-01)")
    inspection_count: int = Field(..., description="Inspections completed that month")
    compliant_count: int = Field(..., description="Compliant inspections that month")
    compliance_rate_percent: float = Field(..., description="compliant/total*100 for the month")


class TrendResponse(BaseModel):
    """GET /dashboard/trends response — monthly aggregates."""

    trends: list[TrendPoint] = Field(default_factory=list, description="Monthly trend data points")
    total_months: int = Field(default=0, description="Number of months in the series")


# ── Category Models ─────────────────────────────────────────────────────────

class CategoryViolation(BaseModel):
    """Violation count for a single product category."""

    category: str = Field(..., description="Category name (e.g. 'Food & Beverage > Packaged Food')")
    violation_count: int = Field(..., description="Number of violations in this category")
    compliance_rate_percent: float = Field(
        ..., description="Compliance rate for this category (0.0–100.0)"
    )


class CategoryResponse(BaseModel):
    """GET /dashboard/categories response — violation distribution."""

    categories: list[CategoryViolation] = Field(
        default_factory=list, description="All categories ranked by violation count"
    )
    total_violations: int = Field(default=0, description="Sum of all category violations")
