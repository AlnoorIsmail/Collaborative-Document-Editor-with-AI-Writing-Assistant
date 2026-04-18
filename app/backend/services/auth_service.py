from datetime import timedelta

from fastapi import status

from app.backend.core.config import settings
from app.backend.core.contracts import utc_now, utc_z
from app.backend.core.errors import ApiError
from app.backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_refresh_token_id,
    get_password_hash,
    verify_password,
)
from app.backend.repositories.refresh_token_repository import RefreshTokenRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.auth import (
    AuthUserResponse,
    LoginResponse,
    MeResponse,
    RefreshResponse,
    RegisterResponse,
    TokenPairResponse,
)


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
    ):
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository

    def register(
        self, *, email: str, display_name: str, password: str
    ) -> RegisterResponse:
        normalized_email = email.strip().lower()
        if self.user_repository.get_by_email(normalized_email):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                error_code="CONFLICT",
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

        if not user:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="No account exists for this email.",
            )

        if not verify_password(password, user.password_hash):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Incorrect password.",
            )

        return LoginResponse(
            **self._issue_token_pair(user.id).model_dump(),
            user=AuthUserResponse(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
            ),
        )

    def refresh(self, *, refresh_token: str) -> RefreshResponse:
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = int(payload["sub"])
            token_id = str(payload["jti"])
        except (KeyError, TypeError, ValueError):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        stored_token = self.refresh_token_repository.get_by_token_id(token_id)
        if (
            stored_token is None
            or stored_token.user_id != user_id
            or stored_token.revoked_at is not None
            or stored_token.expires_at <= utc_now()
        ):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        self.refresh_token_repository.revoke(stored_token, revoked_at=utc_now())
        token_pair = self._issue_token_pair(user.id)
        self.refresh_token_repository.db.commit()
        return RefreshResponse(
            **token_pair.model_dump(),
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

    def _issue_token_pair(self, user_id: int) -> TokenPairResponse:
        refresh_token_id = generate_refresh_token_id()
        refresh_expires_at = utc_now() + timedelta(
            days=settings.refresh_token_expire_days
        )

        self.refresh_token_repository.create(
            user_id=user_id,
            token_id=refresh_token_id,
            expires_at=refresh_expires_at,
        )
        self.refresh_token_repository.db.commit()

        return TokenPairResponse(
            access_token=create_access_token(str(user_id)),
            refresh_token=create_refresh_token(
                str(user_id),
                token_id=refresh_token_id,
            ),
            token_type="bearer",
            access_token_expires_in=settings.access_token_expire_minutes * 60,
            refresh_token_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
        )
