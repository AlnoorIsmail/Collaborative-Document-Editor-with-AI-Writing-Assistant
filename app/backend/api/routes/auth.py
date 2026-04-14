from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.backend.api.deps import get_auth_service, get_current_authenticated_user
from app.backend.models.user import User
from app.backend.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
)
from app.backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a backend user account with a securely hashed password.",
)
def register(
    payload: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
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
    description=(
        "Validate credentials and issue a short-lived access token plus a refresh "
        "token for silent re-authentication."
    ),
)
def login(
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    return auth_service.login(email=payload.email, password=payload.password)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Rotate an authenticated session",
    description="Exchange a valid refresh token for a fresh access token and refresh token.",
)
def refresh(
    payload: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RefreshResponse:
    return auth_service.refresh(refresh_token=payload.refresh_token)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get the current authenticated user",
    description="Resolve the bearer token and return the current backend user profile.",
)
def get_current_user(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MeResponse:
    return auth_service.to_me_response(current_user)
