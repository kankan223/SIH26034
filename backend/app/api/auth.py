"""Authentication endpoints per prd.md §21.

POST /auth/login — authenticate user, return JWT tokens.
POST /auth/refresh — refresh access token using refresh token.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Rate limiter: 5 login attempts per IP per 15 minutes per prd.md §25.1
limiter = Limiter(key_func=get_remote_address)


async def get_db_session() -> AsyncSession:
    """Get a database session. In production, use dependency injection."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Per prd.md §21: POST /auth/login
    - Returns 401 on invalid credentials (no info leakage per prd.md §25.1)
    - Rate limited: 5 attempts per 15 minutes per IP
    """
    from app.core.config import settings as cfg
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(cfg.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, email, password_hash, full_name, role FROM users WHERE email = :email AND is_active = true"),
            {"email": body.email},
        )
        row = result.fetchone()
        user = row

    await engine.dispose()

    if not user or not verify_password(body.password, user.password_hash):
        # Generic error — no info leakage per prd.md §25.1
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_data = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
    }

    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            full_name=user.full_name,
        ),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(body: RefreshRequest) -> AccessTokenResponse:
    """Refresh access token using a valid refresh token.

    Per prd.md §21: POST /auth/refresh
    - Returns 401 if refresh token is expired or invalid
    """
    try:
        payload = verify_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Fetch user to get current role
    from app.core.config import settings as cfg
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(cfg.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, email, role FROM users WHERE id = :id AND is_active = true"),
            {"id": user_id},
        )
        row = result.fetchone()
        user = row

    await engine.dispose()

    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
    })

    return AccessTokenResponse(access_token=access_token)
