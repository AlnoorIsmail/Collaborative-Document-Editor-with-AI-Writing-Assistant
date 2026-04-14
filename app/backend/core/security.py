"""Authentication helpers for password hashing and JWT validation."""

import base64
import hashlib
import hmac
import json
import os
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
    token_type: str


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


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


def get_access_token_ttl_seconds(expires_in_minutes: Optional[int] = None) -> int:
    ttl_minutes = (
        settings.access_token_expire_minutes
        if expires_in_minutes is None
        else expires_in_minutes
    )
    return ttl_minutes * 60


def get_refresh_token_ttl_seconds(expires_in_days: Optional[int] = None) -> int:
    ttl_days = (
        settings.refresh_token_expire_days
        if expires_in_days is None
        else expires_in_days
    )
    return ttl_days * 24 * 60 * 60


def create_access_token(subject: str, expires_in_minutes: Optional[int] = None) -> str:
    return _encode_token(
        {
            "sub": str(subject),
            "type": ACCESS_TOKEN_TYPE,
        },
        expires_in_seconds=get_access_token_ttl_seconds(expires_in_minutes),
    )


def create_refresh_token(
    subject: str,
    *,
    jti: str,
    expires_in_days: Optional[int] = None,
) -> str:
    return _encode_token(
        {
            "sub": str(subject),
            "type": REFRESH_TOKEN_TYPE,
            "jti": jti,
        },
        expires_in_seconds=get_refresh_token_ttl_seconds(expires_in_days),
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_token_type=ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = _decode_token(token, expected_token_type=REFRESH_TOKEN_TYPE)
    if "jti" not in payload or not str(payload["jti"]).strip():
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

    try:
        payload = decode_access_token(token)
    except (TypeError, ValueError):
        from app.backend.core.errors import AppError

        raise AppError(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message="Missing or invalid bearer token.",
        )

    return AuthenticatedPrincipal(
        user_id=str(payload["sub"]),
        role="authenticated",
        token=token,
        token_type=str(payload["type"]),
    )


def _encode_token(payload: dict[str, Any], *, expires_in_seconds: int) -> str:
    if settings.jwt_algorithm != "HS256":
        raise ValueError("Unsupported JWT algorithm configured.")

    issued_at = int(time.time())
    token_payload = {
        **payload,
        "iat": issued_at,
        "exp": issued_at + expires_in_seconds,
    }

    header_b64 = _b64encode(
        json.dumps(
            {"alg": settings.jwt_algorithm, "typ": "JWT"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    payload_b64 = _b64encode(
        json.dumps(token_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def _decode_token(token: str, *, expected_token_type: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token format.") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    provided_signature = _b64decode(signature_b64)

    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid token signature.")

    try:
        header = json.loads(_b64decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid token payload.") from exc

    if header.get("alg") != settings.jwt_algorithm or header.get("typ") != "JWT":
        raise ValueError("Invalid token header.")

    if str(payload.get("type")) != expected_token_type:
        raise ValueError("Unexpected token type.")

    if "sub" not in payload or not str(payload["sub"]).strip():
        raise ValueError("Token subject is missing.")

    expires_at = int(payload.get("exp", 0))
    if expires_at <= int(time.time()):
        raise ValueError("Token has expired.")

    return payload
