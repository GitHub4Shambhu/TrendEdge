"""
TrendEdge Backend - FastAPI Application Entry Point

This is the main application file that configures and runs the FastAPI server.
All routes, middleware, and startup events are configured here.

To run: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.schemas.momentum import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    print("🚀 TrendEdge API starting up...")
    yield
    # Shutdown
    print("👋 TrendEdge API shutting down...")


settings = get_settings()

app = FastAPI(
    title="TrendEdge API",
    description="AI-powered momentum analysis for stocks, ETFs, options, and futures",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "TrendEdge API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow(),
    )
