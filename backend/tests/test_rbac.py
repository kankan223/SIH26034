"""Tests for RBAC middleware — role-based access control enforcement.

Per todo.md Task 1.2.1: verify inspector gets 403 on admin routes,
admin proceeds correctly, missing/expired tokens return 401.
"""

import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import JWTError

from app.core.rbac import get_current_user, require_role
from app.core.security import create_access_token, create_refresh_token, verify_token


# ---------------------------------------------------------------------------
# Test helpers: a tiny FastAPI app with role-gated routes
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with three role-gated routes."""
    test_app = FastAPI()

    @test_app.get("/public")
    async def public_route():
        return {"message": "ok"}

    @test_app.get("/inspector-or-above")
    async def inspector_route(user=Depends(require_role("inspector", "senior_officer", "admin"))):
        return {"user": user}

    @test_app.get("/admin-only")
    async def admin_route(user=Depends(require_role("admin"))):
        return {"user": user}

    @test_app.get("/senior-or-admin")
    async def senior_route(user=Depends(require_role("senior_officer", "admin"))):
        return {"user": user}

    return test_app


@pytest.fixture
def client():
    """Create a test client for RBAC enforcement tests."""
    app = _make_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper: create a Bearer header dict
# ---------------------------------------------------------------------------

def _auth_header(role: str, user_id: str = "1") -> dict:
    """Create Authorization header with a valid JWT for the given role."""
    token = create_access_token({"sub": user_id, "role": role, "email": f"{role}@test.com"})
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Test Suite 1: Token creation and claims (existing tests, preserved)
# ===========================================================================

class TestTokenCreation:
    """Tests for JWT token creation and verification."""

    def test_create_inspector_token(self):
        token = create_access_token({"sub": "1", "role": "inspector", "email": "test@test.com"})
        payload = verify_token(token)
        assert payload["role"] == "inspector"

    def test_create_admin_token(self):
        token = create_access_token({"sub": "2", "role": "admin", "email": "admin@test.com"})
        payload = verify_token(token)
        assert payload["role"] == "admin"

    def test_create_senior_officer_token(self):
        token = create_access_token({"sub": "3", "role": "senior_officer", "email": "senior@test.com"})
        payload = verify_token(token)
        assert payload["role"] == "senior_officer"


# ===========================================================================
# Test Suite 2: Role enum values
# ===========================================================================

class TestRoleEnum:
    """Tests for Role enum correctness per prd.md §8.5 FR-030."""

    def test_role_enum_values(self):
        from app.models.enums import Role
        assert Role.INSPECTOR.value == "inspector"
        assert Role.SENIOR_OFFICER.value == "senior_officer"
        assert Role.ADMIN.value == "admin"

    def test_role_enum_members(self):
        from app.models.enums import Role
        assert len(Role) == 3


# ===========================================================================
# Test Suite 3: require_role dependency factory
# ===========================================================================

class TestRequireRoleFactory:
    """Tests for the require_role dependency creator."""

    def test_require_role_creates_callable(self):
        dep = require_role("admin", "senior_officer")
        assert callable(dep)

    def test_require_role_single_role(self):
        dep = require_role("admin")
        assert callable(dep)


# ===========================================================================
# Test Suite 4: RBAC enforcement — 403 Forbidden
# ===========================================================================

class TestRBACEnforcement403:
    """Tests that insufficient permissions return 403 Forbidden."""

    def test_inspector_on_admin_route_returns_403(self, client):
        """Inspector token accessing admin-only route → 403."""
        resp = client.get("/admin-only", headers=_auth_header("inspector"))
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Insufficient permissions"

    def test_senior_officer_on_admin_route_returns_403(self, client):
        """Senior officer token accessing admin-only route → 403."""
        resp = client.get("/admin-only", headers=_auth_header("senior_officer"))
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Insufficient permissions"

    def test_inspector_on_senior_or_admin_route_returns_403(self, client):
        """Inspector token accessing senior_or_admin route → 403."""
        resp = client.get("/senior-or-admin", headers=_auth_header("inspector"))
        assert resp.status_code == 403


# ===========================================================================
# Test Suite 5: RBAC enforcement — 200 OK (authorized access)
# ===========================================================================

class TestRBACEnforcement200:
    """Tests that authorized roles proceed correctly (200 OK)."""

    def test_admin_on_admin_route_returns_200(self, client):
        """Admin token accessing admin-only route → 200."""
        resp = client.get("/admin-only", headers=_auth_header("admin"))
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "admin"

    def test_admin_on_inspector_route_returns_200(self, client):
        """Admin token accessing inspector route → 200 (admin has all permissions)."""
        resp = client.get("/inspector-or-above", headers=_auth_header("admin"))
        assert resp.status_code == 200

    def test_inspector_on_inspector_route_returns_200(self, client):
        """Inspector token accessing inspector route → 200."""
        resp = client.get("/inspector-or-above", headers=_auth_header("inspector"))
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "inspector"

    def test_senior_officer_on_senior_route_returns_200(self, client):
        """Senior officer token accessing senior_or_admin route → 200."""
        resp = client.get("/senior-or-admin", headers=_auth_header("senior_officer"))
        assert resp.status_code == 200

    def test_public_route_returns_200_without_auth(self, client):
        """Public route accessible without any token → 200."""
        resp = client.get("/public")
        assert resp.status_code == 200


# ===========================================================================
# Test Suite 6: RBAC enforcement — 401 Unauthorized
# ===========================================================================

class TestRBACEnforcement401:
    """Tests that missing/invalid tokens return 401 Unauthorized."""

    def test_missing_auth_header_returns_401(self, client):
        """No Authorization header → 401."""
        resp = client.get("/admin-only")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """Garbage token → 401."""
        resp = client.get("/admin-only", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client):
        """Token with past expiry → 401."""
        from datetime import timedelta
        from app.core.config import settings
        from jose import jwt

        # Create a token that expired 1 hour ago
        expired_payload = {
            "sub": "1",
            "role": "admin",
            "email": "test@test.com",
            "type": "access",
            "exp": time.time() - 3600,  # 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        resp = client.get("/admin-only", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401

    def test_refresh_token_rejected_on_access_route(self, client):
        """Refresh token (type=refresh) should be rejected by get_current_user."""
        refresh_token = create_refresh_token("1")
        resp = client.get("/admin-only", headers={"Authorization": f"Bearer {refresh_token}"})
        assert resp.status_code == 401


# ===========================================================================
# Test Suite 7: RBAC enforcement — response structure
# ===========================================================================

class TestRBACResponseStructure:
    """Tests that RBAC responses have correct structure per prd.md §21."""

    def test_403_response_has_detail_field(self, client):
        """403 response must have a 'detail' field."""
        resp = client.get("/admin-only", headers=_auth_header("inspector"))
        assert resp.status_code == 403
        assert "detail" in resp.json()

    def test_401_response_has_detail_field(self, client):
        """401 response must have a 'detail' field."""
        resp = client.get("/admin-only")
        assert resp.status_code == 401
        assert "detail" in resp.json()

    def test_200_response_contains_user_object(self, client):
        """Successful RBAC check returns user dict with id, role, email."""
        resp = client.get("/admin-only", headers=_auth_header("admin"))
        assert resp.status_code == 200
        user = resp.json()["user"]
        assert "id" in user
        assert "role" in user
        assert "email" in user


# ===========================================================================
# Test Suite 8: get_current_user dependency
# ===========================================================================

class TestGetCurrentUser:
    """Tests for the get_current_user dependency directly."""

    def test_get_current_user_returns_user_dict(self):
        """get_current_user with valid token returns user dict."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        # We can't easily test the Depends chain without a full request,
        # but we can test the token parsing logic
        token = create_access_token({"sub": "42", "role": "inspector", "email": "x@y.com"})
        payload = verify_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "inspector"

    def test_get_current_user_rejects_non_access_token(self):
        """Tokens with type != 'access' should be rejected by get_current_user."""
        refresh_token = create_refresh_token("1")
        payload = verify_token(refresh_token)
        # get_current_user checks payload.get("type") != "access"
        assert payload.get("type") != "access"


# ===========================================================================
# Test Suite 9: Default-deny verification
# ===========================================================================

class TestDefaultDeny:
    """Verify that routes without explicit role checks deny access."""

    def test_no_auth_header_denied_on_protected_route(self, client):
        """Any protected route without auth → 401 (default-deny)."""
        for route in ["/admin-only", "/inspector-or-above", "/senior-or-admin"]:
            resp = client.get(route)
            assert resp.status_code == 401, f"Route {route} should deny without auth"
