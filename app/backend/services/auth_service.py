from datetime import timedelta
from uuid import uuid4

from fastapi import status

from app.backend.core.contracts import utc_z
from app.backend.core.errors import ApiError
from app.backend.core.security import (
    AuthenticatedPrincipal,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_access_token_ttl_seconds,
    get_refresh_token_ttl_seconds,
    get_password_hash,
    verify_password,
)
from app.backend.repositories.refresh_token_repository import RefreshTokenRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.auth import (
    AuthUserResponse,
    LoginResponse,
    MeResponse,
    RefreshTokenResponse,
    RegisterResponse,
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
                error_code="CONFLICT_DETECTED",
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

        access_token, refresh_token = self._issue_token_pair(user_id=user.id)
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_in_seconds=get_access_token_ttl_seconds(),
            refresh_token_expires_in_seconds=get_refresh_token_ttl_seconds(),
            user=AuthUserResponse(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
            ),
        )

    def refresh(self, *, refresh_token: str) -> RefreshTokenResponse:
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = int(payload["sub"])
            jti = str(payload["jti"])
        except (TypeError, ValueError):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        token_record = self.refresh_token_repository.get_by_jti(jti)
        if token_record is None or token_record.user_id != user_id:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        if (
            token_record.revoked_at is not None
            or token_record.expires_at <= self._utc_now()
        ):
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Invalid or expired refresh token.",
            )

        self.refresh_token_repository.revoke(
            token_record,
            revoked_at=self._utc_now(),
        )
        access_token, next_refresh_token = self._issue_token_pair(user_id=user.id)
        self.refresh_token_repository.db.commit()
        return RefreshTokenResponse(
            access_token=access_token,
            refresh_token=next_refresh_token,
            access_token_expires_in_seconds=get_access_token_ttl_seconds(),
            refresh_token_expires_in_seconds=get_refresh_token_ttl_seconds(),
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

    def get_current_user_from_principal(self, principal: AuthenticatedPrincipal):
        try:
            user_id = int(principal.user_id)
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

    def _issue_token_pair(self, *, user_id: int) -> tuple[str, str]:
        refresh_jti = uuid4().hex
        refresh_expires_at = self._utc_now() + timedelta(
            seconds=get_refresh_token_ttl_seconds()
        )
        self.refresh_token_repository.create(
            user_id=user_id,
            jti=refresh_jti,
            expires_at=refresh_expires_at,
        )
        self.refresh_token_repository.db.commit()
        return (
            create_access_token(str(user_id)),
            create_refresh_token(str(user_id), jti=refresh_jti),
        )

    def _utc_now(self):
        from app.backend.core.contracts import utc_now

        return utc_now()
