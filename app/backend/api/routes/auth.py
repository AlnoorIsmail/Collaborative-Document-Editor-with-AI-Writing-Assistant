from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.backend.core.database import get_db
from app.backend.core.errors import ApiError
from app.backend.core.security import bearer_scheme
from app.backend.models.user import User
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db))


def get_bearer_token(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message="Authorization token is missing.",
        )

    if credentials is None or not credentials.credentials.strip():
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message="Authorization token is invalid.",
        )

    return credentials.credentials.strip()


def get_current_authenticated_user(
    token: str = Depends(get_bearer_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    return auth_service.get_current_user(token)


def get_optional_authenticated_user(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[User]:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    if credentials is None or not credentials.credentials.strip():
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message="Authorization token is invalid.",
        )

    return auth_service.get_current_user(credentials.credentials.strip())


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
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


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    return auth_service.login(email=payload.email, password=payload.password)


@router.get("/me", response_model=MeResponse)
def get_current_user(
    current_user: User = Depends(get_current_authenticated_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    return auth_service.to_me_response(current_user)
