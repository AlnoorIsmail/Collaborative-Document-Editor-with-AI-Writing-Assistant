from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.backend.api.deps import (
    get_current_authenticated_user,
)
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.refresh_token_repository import RefreshTokenRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(
        UserRepository(db),
        RefreshTokenRepository(db),
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user account",
    description="Create a new backend user account with a securely hashed password.",
)
def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RegisterResponse:
    return auth_service.register(
        email=payload.email,
        display_name=payload.display_name,
        password=payload.password,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate a user",
    description="Validate credentials and return a short-lived JWT access token plus a refresh token.",
)
def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    return auth_service.login(email=payload.email, password=payload.password)


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Refresh an authenticated session",
    description="Rotate a valid refresh token and issue a fresh access/refresh token pair.",
)
def refresh_access_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    return auth_service.refresh(refresh_token=payload.refresh_token)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current user",
    description="Return the user represented by the provided bearer access token.",
)
def get_current_user(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    return auth_service.to_me_response(current_user)
