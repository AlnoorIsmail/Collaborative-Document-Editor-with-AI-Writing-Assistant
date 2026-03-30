"""Authentication scaffolding for protected endpoints."""

from dataclasses import dataclass

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.backend.core.errors import AppError
from apps.backend.schemas.common import ErrorCode

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    role: str
    token: str


def get_principal_from_credentials(
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthenticatedPrincipal:
    """Accept any non-empty bearer token for scaffold-level bootstrapping."""

    if credentials is None or not credentials.credentials.strip():
        raise AppError(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message="Missing or invalid bearer token.",
        )

    token = credentials.credentials.strip()
    user_id = "usr_123"
    role = "editor"

    if ":" in token:
        candidate_user_id, candidate_role = token.split(":", 1)
        if candidate_user_id:
            user_id = candidate_user_id
        if candidate_role:
            role = candidate_role

    return AuthenticatedPrincipal(user_id=user_id, role=role, token=token)
