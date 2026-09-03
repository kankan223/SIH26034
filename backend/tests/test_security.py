"""Tests for security utilities — password hashing and JWT tokens."""

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)


class TestPasswordHashing:
    """Tests for bcrypt password hashing per prd.md §25.1."""

    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("testpassword")
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = hash_password("testpassword")
        assert verify_password("testpassword", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("testpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_is_deterministic_but_unique(self):
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2  # bcrypt uses random salt
        assert verify_password("samepassword", h1) is True
        assert verify_password("samepassword", h2) is True


class TestAccessToken:
    """Tests for JWT access token creation and verification."""

    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user-123", "role": "inspector"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_correct_claims(self):
        token = create_access_token({"sub": "user-123", "role": "inspector"})
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "inspector"
        assert "exp" in payload
        assert payload["type"] == "access"

    def test_verify_token_invalid_token(self):
        with pytest.raises(JWTError):
            verify_token("invalid.token.here")


class TestRefreshToken:
    """Tests for JWT refresh token creation and verification."""

    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_refresh_token_contains_correct_claims(self):
        token = create_refresh_token("user-123")
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        assert "exp" in payload
        assert payload["type"] == "refresh"
