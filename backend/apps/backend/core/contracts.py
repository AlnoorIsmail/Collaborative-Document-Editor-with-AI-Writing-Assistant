from datetime import datetime, timezone

from fastapi import status

from apps.backend.core.errors import ApiError


def parse_prefixed_id(value: str, prefix: str) -> int:
    expected_prefix = prefix + "_"
    if not value.startswith(expected_prefix):
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            message="Invalid identifier format.",
        )
    try:
        return int(value[len(expected_prefix):])
    except ValueError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            message="Invalid identifier format.",
        ) from exc


def prefixed_id(prefix: str, value: int) -> str:
    return "{prefix}_{value}".format(prefix=prefix, value=value)


def parse_utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            message="Invalid datetime format.",
        ) from exc
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def utc_z(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
