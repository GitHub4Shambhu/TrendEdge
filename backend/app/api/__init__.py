"""API module initialization."""

from fastapi import APIRouter

from app.api.alerts import router as alerts_router
from app.api.dashboard import router as dashboard_router

api_router = APIRouter()
api_router.include_router(dashboard_router)
api_router.include_router(alerts_router)

__all__ = ["api_router"]
