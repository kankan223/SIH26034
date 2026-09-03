"""Docket Legal Metrology Compliance System — FastAPI Application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

# Rate limiter — per prd.md §25.1
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Docket — Legal Metrology Compliance API",
    description="Automated compliance checking for packaged commodities under LMPC Rules 2011",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
origins = [origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
from app.api.auth import router as auth_router
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": "Docket Legal Metrology Compliance API",
        "version": "0.1.0",
        "docs": "/docs",
    }
