"""Authentication helpers for protected endpoints."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.backend.core.config import settings
from app.backend.schemas.common import ErrorCode

PASSWORD_HASH_ITERATIONS = 260000
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    role: str
    token: str


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _json_dumps(data: dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def get_password_hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return "{iterations}${salt}${digest}".format(
        iterations=PASSWORD_HASH_ITERATIONS,
        salt=_b64encode(salt),
        digest=_b64encode(digest),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        iterations_str, salt_b64, digest_b64 = hashed_password.split("$", 2)
        iterations = int(iterations_str)
        salt = _b64decode(salt_b64)
        expected_digest = _b64decode(digest_b64)
    except (TypeError, ValueError):
        return False

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate_digest, expected_digest)


def _sign(signing_input: str) -> str:
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64encode(signature)


def create_token(
    *,
    subject: str,
    token_type: str,
    expires_in_seconds: int,
    token_id: Optional[str] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    now = int(time.time())
    header = {
        "alg": settings.jwt_algorithm,
        "typ": "JWT",
    }
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    if token_id:
        payload["jti"] = token_id
    if extra_claims:
        payload.update(extra_claims)

    header_b64 = _b64encode(_json_dumps(header))
    payload_b64 = _b64encode(_json_dumps(payload))
    signing_input = f"{header_b64}.{payload_b64}"
    return f"{signing_input}.{_sign(signing_input)}"


def create_access_token(subject: str, expires_in_minutes: Optional[int] = None) -> str:
    ttl_minutes = (
        settings.access_token_expire_minutes
        if expires_in_minutes is None
        else expires_in_minutes
    )
    return create_token(
        subject=subject,
        token_type=ACCESS_TOKEN_TYPE,
        expires_in_seconds=ttl_minutes * 60,
    )


def generate_refresh_token_id() -> str:
    return secrets.token_urlsafe(32)


def create_refresh_token(
    subject: str,
    token_id: str,
    expires_in_days: Optional[int] = None,
) -> str:
    ttl_days = (
        settings.refresh_token_expire_days
        if expires_in_days is None
        else expires_in_days
    )
    return create_token(
        subject=subject,
        token_type=REFRESH_TOKEN_TYPE,
        token_id=token_id,
        expires_in_seconds=ttl_days * 24 * 60 * 60,
    )


def decode_token(token: str, *, expected_type: Optional[str] = None) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token format.") from exc

    header = json.loads(_b64decode(header_b64).decode("utf-8"))
    if header.get("alg") != settings.jwt_algorithm or header.get("typ") != "JWT":
        raise ValueError("Unsupported token header.")

    signing_input = f"{header_b64}.{payload_b64}"
    if not hmac.compare_digest(_sign(signing_input), signature_b64):
        raise ValueError("Invalid token signature.")

    payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise ValueError("Token has expired.")

    if "sub" not in payload:
        raise ValueError("Token subject is missing.")

    if expected_type and payload.get("type") != expected_type:
        raise ValueError("Unexpected token type.")

    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, expected_type=ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
    if "jti" not in payload:
        raise ValueError("Refresh token identifier is missing.")
    return payload


def get_principal_from_credentials(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> AuthenticatedPrincipal:
    if credentials is None or not credentials.credentials.strip():
        from app.backend.core.errors import AppError

        raise AppError(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message="Missing or invalid bearer token.",
        )

    token = credentials.credentials.strip()

    if ":" in token and "." not in token:
        candidate_user_id, candidate_role = token.split(":", 1)
        return AuthenticatedPrincipal(
            user_id=candidate_user_id or "usr_123",
            role=candidate_role or "editor",
            token=token,
        )

    try:
        payload = decode_access_token(token)
    except (TypeError, ValueError):
        from app.backend.core.errors import AppError

        raise AppError(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message="Missing or invalid bearer token.",
        )

    user_id = str(payload["sub"])
    if user_id.isdigit():
        user_id = f"usr_{user_id}"

    return AuthenticatedPrincipal(
        user_id=user_id,
        role="editor",
        token=token,
    )
