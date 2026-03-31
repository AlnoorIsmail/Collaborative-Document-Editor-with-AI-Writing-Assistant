"""Top-level API router for the merged backend."""

from fastapi import APIRouter

from app.backend.api.routes.ai import router as ai_router
from app.backend.api.routes.auth import router as auth_router
from app.backend.api.routes.documents import router as documents_router
from app.backend.api.routes.invitations import router as invitations_router
from app.backend.api.routes.permissions import router as permissions_router
from app.backend.api.routes.sessions import router as sessions_router
from app.backend.api.routes.share_links import router as share_links_router
from app.backend.api.routes.versions import router as versions_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(versions_router)
api_router.include_router(permissions_router)
api_router.include_router(invitations_router)
api_router.include_router(share_links_router)
api_router.include_router(sessions_router)
api_router.include_router(ai_router)
