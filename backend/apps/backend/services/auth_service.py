from fastapi import status

from apps.backend.core.contracts import utc_z
from apps.backend.core.errors import ApiError
from apps.backend.core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from apps.backend.repositories.user_repository import UserRepository
from apps.backend.schemas.auth import AuthUserResponse, LoginResponse, MeResponse, RegisterResponse


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def register(self, *, email: str, display_name: str, password: str) -> RegisterResponse:
        normalized_email = email.strip().lower()
        if self.user_repository.get_by_email(normalized_email):
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="A user with this email already exists.",
            )

        user = self.user_repository.create(
            email=normalized_email,
            display_name=display_name.strip(),
            password_hash=get_password_hash(password),
        )
        return RegisterResponse(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            account_status="active",
            created_at=utc_z(user.created_at),
        )

    def login(self, *, email: str, password: str) -> LoginResponse:
        normalized_email = email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)

        if not user or not verify_password(password, user.password_hash):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid email or password.",
            )

        return LoginResponse(
            access_token=create_access_token(str(user.id)),
            user=AuthUserResponse(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
            ),
        )

    def get_current_user(self, token: str):
        try:
            payload = decode_access_token(token)
            user_id = int(payload["sub"])
        except (TypeError, ValueError):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired token.",
            )

        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired token.",
            )

        return user

    def to_me_response(self, user) -> MeResponse:
        return MeResponse(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            account_status="active",
        )
