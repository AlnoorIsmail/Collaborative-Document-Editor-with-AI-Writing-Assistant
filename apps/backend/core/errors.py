"""Shared exception types and HTTP handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.backend.schemas.common import ErrorCode, ErrorResponse


class AppError(Exception):
    """Structured application error that maps cleanly to the API contract."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.retryable = retryable


def _error_body(error_code: ErrorCode, message: str, retryable: bool = False) -> dict[str, Any]:
    return ErrorResponse(
        error_code=error_code,
        message=message,
        retryable=retryable,
    ).model_dump(mode="json")


async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.error_code, exc.message, exc.retryable),
    )


async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {"msg": "Request validation failed."}
    location = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
    detail = first_error.get("msg", "Request validation failed.")
    prefix = f"{location}: " if location else ""
    return JSONResponse(
        status_code=422,
        content=_error_body(ErrorCode.VALIDATION_ERROR, f"{prefix}{detail}"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
