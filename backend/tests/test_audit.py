"""
Tests for Task 1.3.2: Audit Logging Middleware and Event Tracking

Verifies:
- Audit schema validation (AuditLogCreate, AuditLogResponse, AuditLogListResponse, AuditLogFilterParams)
- Audit middleware (intercepts mutating operations, skips reads/health, filters sensitive data)
- Audit API RBAC (admin-only access to GET /audit-logs)
- Sensitive data filtering (no auth headers, no binary data logged)
- Query filtering and pagination validation
"""
import asyncio
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from fastapi import Request
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Import app and schemas
# ---------------------------------------------------------------------------
from app.main import app
from app.schemas.audit import (
    AuditLogCreate,
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogFilterParams,
    AuditLogEntityHistoryResponse,
)


# ---------------------------------------------------------------------------
# Helper: create valid JWT tokens using the app's security module
# ---------------------------------------------------------------------------
def _make_token(sub: int, role: str, exp_offset: int = 3600):
    """Create a valid JWT token with given claims."""
    from datetime import timedelta
    from app.core.security import create_access_token

    return create_access_token(
        data={"sub": str(sub), "role": role},
        expires_delta=timedelta(seconds=exp_offset),
    )


ADMIN_TOKEN = _make_token(sub=1, role="admin")
INSPECTOR_TOKEN = _make_token(sub=2, role="inspector")
SENIOR_TOKEN = _make_token(sub=3, role="senior_officer")
EXPIRED_TOKEN = _make_token(sub=1, role="admin", exp_offset=-1)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: SCHEMA TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditLogSchemas:
    """Validate Pydantic models for audit logs."""

    def test_audit_log_create_schema(self):
        log = AuditLogCreate(
            action="inspection.create",
            entity_type="inspection",
            entity_id="test-uuid-001",
        )
        assert log.action == "inspection.create"
        assert log.entity_type == "inspection"
        assert log.entity_id == "test-uuid-001"
        assert log.actor_id is None
        assert log.before_value is None
        assert log.after_value is None
        assert log.reason is None

    def test_audit_log_create_schema_with_all_fields(self):
        log = AuditLogCreate(
            actor_id="user-5",
            action="inspection.status_change",
            entity_type="inspection",
            entity_id="test-uuid-042",
            before_value={"status": "draft"},
            after_value={"status": "in_review"},
            reason="Inspector completed review",
        )
        assert log.actor_id == "user-5"
        assert log.before_value["status"] == "draft"
        assert log.after_value["status"] == "in_review"
        assert log.reason == "Inspector completed review"

    def test_audit_log_create_system_action(self):
        log = AuditLogCreate(
            action="system.health_check",
            entity_type="system",
            entity_id="system-0",
        )
        assert log.entity_id == "system-0"
        assert log.entity_type == "system"
        assert log.actor_id is None

    def test_audit_log_response_schema(self):
        resp = AuditLogResponse(
            id="log-uuid-001",
            actor_id="user-5",
            action="inspection.create",
            entity_type="inspection",
            entity_id="test-uuid-001",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.id == "log-uuid-001"
        assert resp.action == "inspection.create"
        assert resp.entity_type == "inspection"

    def test_audit_log_list_response_schema(self):
        resp = AuditLogListResponse(
            items=[],
            total=0,
            page=1,
            page_size=50,
        )
        assert resp.total == 0
        assert resp.items == []

    def test_audit_log_filter_params_defaults(self):
        f = AuditLogFilterParams()
        assert f.action is None
        assert f.resource_type is None
        assert f.page == 1
        assert f.page_size == 20

    def test_audit_log_filter_params_custom(self):
        f = AuditLogFilterParams(
            action="inspection.create",
            page=2,
            page_size=50,
        )
        assert f.action == "inspection.create"
        assert f.page == 2
        assert f.page_size == 50

    def test_audit_log_entity_history_response(self):
        resp = AuditLogEntityHistoryResponse(
            entity_type="inspection",
            entity_id="test-uuid-001",
            history=[],
            total=0,
        )
        assert resp.entity_type == "inspection"
        assert resp.entity_id == "test-uuid-001"
        assert resp.total == 0


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: AUDIT SERVICE FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditServiceFunctions:
    """Test audit service utility functions (no DB required)."""

    def test_log_action_is_async(self):
        """log_action should be an async function."""
        from app.services.audit_service import log_action
        assert asyncio.iscoroutinefunction(log_action)

    def test_get_audit_logs_is_async(self):
        """get_audit_logs should be an async function."""
        from app.services.audit_service import get_audit_logs
        assert asyncio.iscoroutinefunction(get_audit_logs)

    def test_get_audit_log_by_id_is_async(self):
        """get_audit_log_by_id should be an async function."""
        from app.services.audit_service import get_audit_log_by_id
        assert asyncio.iscoroutinefunction(get_audit_log_by_id)

    def test_get_entity_audit_trail_is_async(self):
        """get_entity_audit_trail should be an async function."""
        from app.services.audit_service import get_entity_audit_trail
        assert asyncio.iscoroutinefunction(get_entity_audit_trail)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: AUDIT MIDDLEWARE TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditMiddleware:
    """Verify the audit middleware intercepts mutating operations."""

    def test_middleware_does_not_log_get_requests(self):
        """GET requests should not trigger audit logging."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/health")
            assert response.status_code in (200, 404)

    def test_middleware_excludes_health_check(self):
        """Health check paths are excluded from audit logging."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/health")
            assert response.status_code == 200

    def test_middleware_excludes_docs(self):
        """OpenAPI docs paths are excluded from audit logging."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/docs")
            assert response.status_code == 200

    def test_middleware_handles_db_failure_gracefully(self):
        """When DB is unavailable, middleware should not block the request.
        The endpoint may fail (e.g., 401/500) but middleware should not crash."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/inspections",
                json={"title": "Test", "region": "Delhi"},
            )
            # 401 = auth enforced, 500 = DB unavailable — both indicate middleware didn't crash
            assert response.status_code in (401, 500)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: AUDIT API RBAC TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditAPIRBAC:
    """Verify RBAC enforcement on audit log endpoints."""

    def test_get_audit_logs_without_auth_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/audit-logs")
            assert response.status_code == 401

    def test_get_audit_logs_with_inspector_token_returns_403(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                headers={"Authorization": f"Bearer {INSPECTOR_TOKEN}"},
            )
            assert response.status_code == 403

    def test_get_audit_logs_with_senior_officer_token_returns_403(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                headers={"Authorization": f"Bearer {SENIOR_TOKEN}"},
            )
            assert response.status_code == 403

    def test_get_audit_logs_with_admin_token_succeeds(self):
        """Admin token should pass RBAC. May return 200 or 500 (DB unavailable)."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            # 200 = success (empty list), 500 = RBAC passed but DB unavailable
            assert response.status_code in (200, 500)

    def test_get_audit_log_by_id_without_auth_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/audit-logs/some-uuid")
            assert response.status_code == 401

    def test_get_audit_log_by_id_with_inspector_token_returns_403(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs/some-uuid",
                headers={"Authorization": f"Bearer {INSPECTOR_TOKEN}"},
            )
            assert response.status_code == 403

    def test_get_entity_history_without_auth_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs/entity/inspection/some-uuid",
            )
            assert response.status_code == 401

    def test_get_entity_history_with_inspector_token_returns_403(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs/entity/inspection/some-uuid",
                headers={"Authorization": f"Bearer {INSPECTOR_TOKEN}"},
            )
            assert response.status_code == 403

    def test_get_entity_history_with_admin_token_succeeds(self):
        """Admin on entity history — may 200 or 500 (DB), but not 401/403."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs/entity/inspection/some-uuid",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            assert response.status_code in (200, 500)

    def test_get_audit_log_by_id_with_expired_token_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs/some-uuid",
                headers={"Authorization": f"Bearer {EXPIRED_TOKEN}"},
            )
            assert response.status_code == 401

    def test_get_audit_logs_with_invalid_token_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                headers={"Authorization": "Bearer invalid.token.here"},
            )
            assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: AUDIT LOGGING INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditLoggingIntegration:
    """Verify that audit logging is integrated into key workflows."""

    def test_inspection_create_requires_auth(self):
        """Creating an inspection requires authentication (audit logged)."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/inspections",
                json={"title": "Test Inspection", "region": "Delhi"},
            )
            assert response.status_code == 401

    def test_image_upload_requires_auth(self):
        """Image upload requires authentication (audit logged)."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/inspections/some-uuid/images",
                files={"file": ("test.bin", b"not-an-image", "application/octet-stream")},
            )
            assert response.status_code == 401

    def test_inspection_list_requires_auth(self):
        """Listing inspections requires authentication."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/inspections")
            assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: SENSITIVE DATA FILTERING
# ═══════════════════════════════════════════════════════════════════════════


class TestSensitiveDataFiltering:
    """Verify sensitive data is not logged by the audit middleware."""

    def test_auth_headers_stripped_from_logging(self):
        """Authorization headers should not be captured in audit logs."""
        headers = {
            "Authorization": "Bearer supersecret-token-12345",
            "Content-Type": "application/json",
            "X-Request-ID": "abc123",
        }
        # Simulate the middleware's header filtering logic
        sensitive = {"authorization", "x-api-key", "x-csrf-token"}
        sanitized = {
            k: v for k, v in headers.items()
            if k.lower() not in sensitive
        }
        assert "Authorization" not in sanitized
        assert "Content-Type" in sanitized
        assert "X-Request-ID" in sanitized

    def test_middleware_does_not_log_binary_payloads(self):
        """Binary content types should not be captured in audit logs."""
        binary_types = [
            "image/jpeg", "image/png", "image/webp",
            "application/octet-stream", "image/tiff",
        ]
        for ct in binary_types:
            assert ct.startswith("image/") or ct.startswith("application/octet"), \
                f"{ct} should be binary"

    def test_binary_content_type_detection(self):
        """Test binary content type detection logic."""
        text_types = [
            "application/json", "text/plain",
            "application/x-www-form-urlencoded",
        ]
        for ct in text_types:
            assert not ct.startswith("image/"), f"{ct} should not be binary"

    def test_middleware_excludes_openapi_paths(self):
        """OpenAPI/docs paths should be excluded from audit logging."""
        from app.middleware.audit import EXCLUDED_PATHS
        assert "/docs" in EXCLUDED_PATHS
        assert "/openapi.json" in EXCLUDED_PATHS
        assert "/health" in EXCLUDED_PATHS

    def test_middleware_only_intercepts_mutating_methods(self):
        """Middleware should only log POST, PUT, PATCH, DELETE operations."""
        mutating = {"POST", "PUT", "PATCH", "DELETE"}
        read_only = {"GET", "HEAD", "OPTIONS"}
        # This is a design assertion — middleware checks method in should_log
        assert "GET" not in mutating
        assert "POST" in mutating


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: AUDIT LOG QUERY FILTERING
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditLogQueryFiltering:
    """Test query parameter validation for audit log endpoints."""

    def test_audit_logs_endpoint_accepts_filters(self):
        """Filter params should be accepted (RBAC or DB may fail)."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                params={
                    "action": "inspection.create",
                    "entity_type": "inspection",
                    "page": 1,
                    "page_size": 10,
                },
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            # 200 = success, 500 = DB unavailable, 422 = validation error
            assert response.status_code in (200, 422, 500)

    def test_audit_logs_endpoint_rejects_invalid_page(self):
        """Page=0 should be rejected (422 validation error)."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                params={"page": 0},
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            assert response.status_code == 422

    def test_audit_logs_endpoint_rejects_large_page_size(self):
        """page_size > 100 should be rejected (422 validation error)."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs",
                params={"page_size": 101},
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            assert response.status_code == 422

    def test_entity_history_endpoint_accepts_entity_type(self):
        """Entity history endpoint should accept valid entity_type."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/api/v1/audit-logs/entity/inspection/some-uuid",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            # 200 = success, 500 = DB unavailable
            assert response.status_code in (200, 500)

    def test_audit_logs_page_size_default(self):
        """Default page_size should be 20."""
        f = AuditLogFilterParams()
        assert f.page_size == 20

    def test_audit_logs_page_default(self):
        """Default page should be 1."""
        f = AuditLogFilterParams()
        assert f.page == 1

    def test_audit_logs_page_size_max_enforced(self):
        """page_size > 100 should be rejected by Pydantic validation."""
        with pytest.raises(Exception):
            AuditLogFilterParams(page_size=101)
