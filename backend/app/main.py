"""Docket Legal Metrology Compliance System — FastAPI Application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Docket — Legal Metrology Compliance API",
    description="Automated compliance checking for packaged commodities under LMPC Rules 2011",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
origins = [origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
