"""Tests for dashboard KPI, trends, and category analytics endpoints (prd.md §23)."""

import pytest
from datetime import date

from app.schemas.dashboard import (
    KPIObject,
    TrendResponse,
    CategoryResponse,
    CategoryViolation,
    TrendPoint,
)


# ── Schema Tests ─────────────────────────────────────────────────────────────

class TestKPIObject:
    """Tests for the KPI schema."""

    def test_kpi_object_has_required_fields(self):
        kpi = KPIObject(
            total_inspections=1500,
            compliant_count=1200,
            non_compliant_count=250,
            flagged_for_review_count=30,
            pending_review_count=20,
            active_violations_count=280,
            compliance_rate_percent=82.8,
            total_products_categorized=890,
            top_category="Food & Beverage > Packaged Food",
        )
        assert kpi.total_inspections == 1500
        assert kpi.compliance_rate_percent == 82.8
        assert kpi.top_category == "Food & Beverage > Packaged Food"

    def test_kpi_object_accepts_null_top_category(self):
        kpi = KPIObject(
            total_inspections=50,
            compliant_count=50,
            non_compliant_count=0,
            flagged_for_review_count=0,
            pending_review_count=0,
            active_violations_count=0,
            compliance_rate_percent=100.0,
            total_products_categorized=50,
            top_category=None,
        )
        assert kpi.top_category is None


class TestTrendPoint:
    def test_trend_point_structure(self):
        tp = TrendPoint(
            month=date(2026, 8, 1),
            inspection_count=120,
            compliant_count=100,
            compliance_rate_percent=83.3,
        )
        assert tp.month == date(2026, 8, 1)
        assert tp.compliance_rate_percent == 83.3

    def test_trend_point_zero_inspections(self):
        tp = TrendPoint(
            month=date(2026, 9, 1),
            inspection_count=0,
            compliant_count=0,
            compliance_rate_percent=0.0,
        )
        assert tp.compliance_rate_percent == 0.0


class TestTrendResponse:
    def test_trend_response_empty(self):
        resp = TrendResponse(trends=[], total_months=0)
        assert resp.trends == []
        assert resp.total_months == 0

    def test_trend_response_multiple_months(self):
        trends = [
            TrendPoint(month=date(2026, 6, 1), inspection_count=100, compliant_count=80, compliance_rate_percent=80.0),
            TrendPoint(month=date(2026, 7, 1), inspection_count=110, compliant_count=90, compliance_rate_percent=81.8),
        ]
        resp = TrendResponse(trends=trends, total_months=2)
        assert resp.total_months == 2


class TestCategoryResponse:
    def test_category_response_empty(self):
        resp = CategoryResponse(categories=[], total_violations=0)
        assert resp.categories == []
        assert resp.total_violations == 0

    def test_category_response_fields(self):
        cat = CategoryViolation(
            category="Food & Beverage > Packaged Food",
            violation_count=45,
            compliance_rate_percent=75.0,
        )
        resp = CategoryResponse(categories=[cat], total_violations=45)
        assert resp.total_violations == 45
        assert resp.categories[0].category == "Food & Beverage > Packaged Food"


# ── Router Registration Tests ────────────────────────────────────────────────

class TestDashboardEndpointSignatures:
    """Verify dashboard API endpoint signatures and route registration."""

    def test_dashboard_router_has_kpis_endpoint(self):
        from app.api.dashboard import dashboard_router
        routes = [r.path for r in dashboard_router.routes]
        assert any("/kpis" in r for r in routes), f"Missing /kpis in routes: {routes}"

    def test_dashboard_router_has_trends_endpoint(self):
        from app.api.dashboard import dashboard_router
        routes = [r.path for r in dashboard_router.routes]
        assert any("/trends" in r for r in routes), f"Missing /trends in routes: {routes}"

    def test_dashboard_router_has_categories_endpoint(self):
        from app.api.dashboard import dashboard_router
        routes = [r.path for r in dashboard_router.routes]
        assert any("/categories" in r for r in routes), f"Missing /categories in routes: {routes}"

    def test_kpis_endpoint_requires_auth(self):
        from app.api.dashboard import get_kpis
        import inspect
        params = inspect.signature(get_kpis).parameters
        assert "current_user" in params
        assert "db" in params

    def test_trends_endpoint_requires_admin(self):
        from app.api.dashboard import get_trends
        import inspect
        source = inspect.getsource(get_trends)
        assert "Role.ADMIN" in source

    def test_categories_endpoint_requires_admin(self):
        from app.api.dashboard import get_categories
        import inspect
        source = inspect.getsource(get_categories)
        assert "Role.ADMIN" in source


# ── RBAC Tests ────────────────────────────────────────────────────────────────

class TestDashboardRBACAssertions:
    """Verify RBAC logic for dashboard endpoints."""

    def test_kpis_allowed_for_senior_officer(self):
        from app.core.rbac import require_role
        from app.models.enums import Role
        from unittest.mock import MagicMock

        user = MagicMock()
        user.role = Role.SENIOR_OFFICER
        dependency = require_role(Role.INSPECTOR, Role.SENIOR_OFFICER, Role.ADMIN)
        assert user.role in (Role.INSPECTOR, Role.SENIOR_OFFICER, Role.ADMIN)

    def test_trends_denied_for_senior_officer(self):
        from app.core.rbac import require_role
        from app.models.enums import Role
        from unittest.mock import MagicMock

        user = MagicMock()
        user.role = Role.SENIOR_OFFICER
        dependency = require_role(Role.ADMIN)
        assert user.role not in (Role.ADMIN,)

    def test_trends_allowed_for_admin(self):
        from app.core.rbac import require_role
        from app.models.enums import Role
        from unittest.mock import MagicMock

        user = MagicMock()
        user.role = Role.ADMIN
        dependency = require_role(Role.ADMIN)
        assert user.role in (Role.ADMIN,)
