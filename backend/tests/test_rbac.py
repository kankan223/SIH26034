"""Tests for RBAC middleware."""

import pytest
from jose import JWTError

from app.core.security import create_access_token, verify_token
from app.core.rbac import get_current_user, require_role


class TestRBAC:
    """Tests for role-based access control dependencies."""

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

    def test_role_enum_values(self):
        from app.models.enums import Role
        assert Role.INSPECTOR.value == "inspector"
        assert Role.SENIOR_OFFICER.value == "senior_officer"
        assert Role.ADMIN.value == "admin"

    def test_require_role_creator(self):
        """Test that require_role creates a callable dependency."""
        dep = require_role("admin", "senior_officer")
        assert callable(dep)
