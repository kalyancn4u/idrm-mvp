"""Uniform error envelope + handlers.

Every error renders as:
    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

_CODE_STATUS = {
    "validation_error": 422,
    "unauthorized": 401,
    "token_expired": 401,
    "invalid_token": 401,
    "malformed_token": 401,
    "session_not_found": 401,
    "session_revoked": 401,
    "session_expired": 401,
    "session_idle_expired": 401,
    "user_not_found": 401,
    "account_disabled": 401,
    "token_version_mismatch": 401,
    "invalid_credentials": 401,
    "forbidden": 403,
    "account_locked": 403,
    "not_found": 404,
    "email_exists": 409,
    "conflict": 409,
    "invalid_transition": 409,
    "already_accepted": 409,
    "cannot_modify": 409,
    "file_too_large": 413,
    "unsupported_media_type": 415,
    "rate_limited": 429,
    "internal_error": 500,
}


class AppError(Exception):
    """A domain error with a stable machine-readable code."""

    def __init__(
        self,
        status_code: int | None = None,
        code: str = "internal_error",
        message: str = "Something went wrong.",
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code or _CODE_STATUS.get(code, 500)
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _envelope(code: str, message: str, details: dict | None = None) -> dict:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error", "One or more fields are invalid.",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "unauthorized", 403: "forbidden", 404: "not_found",
            405: "method_not_allowed", 429: "rate_limited",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        log.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )

