"""FastAPI application entrypoint for the merged backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.api.router import api_router
from app.backend.core.config import get_settings
from app.backend.core.database import Base, engine
from app.backend.core.errors import register_exception_handlers
from app.backend.schemas.common import HealthResponse

from app.backend.models import document as _document
from app.backend.models import document_permission as _document_permission
from app.backend.models import document_version as _document_version
from app.backend.models import invitation as _invitation
from app.backend.models import share_link as _share_link
from app.backend.models import user as _user


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
