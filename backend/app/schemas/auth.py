"""Pydantic schemas for authentication endpoints."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Login request body."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Login response body per prd.md §21."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    """Token refresh request body."""
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """Token refresh response body."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User info in auth responses."""
    id: str
    email: str
    role: str
    full_name: str

    model_config = {"from_attributes": True}
