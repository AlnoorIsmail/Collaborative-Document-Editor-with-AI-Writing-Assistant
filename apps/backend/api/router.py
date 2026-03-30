"""Top-level API router for the backend scaffold."""

from fastapi import APIRouter

from apps.backend.api.routes.ai import router as ai_router
from apps.backend.api.routes.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(sessions_router)
api_router.include_router(ai_router)
