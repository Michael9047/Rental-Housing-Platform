"""Structured logging, request/response middleware, and global exception handlers."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()

SENSITIVE_FIELDS = {"password", "phone", "email", "secret", "token", "authorization", "cookie"}
SENSITIVE_PATTERNS = [
    (re.compile(r"(\\b\\d{3}-?\\d{2}-?\\d{4}\\b)|(\\b\\d{3}\\s?\\d{4}\\s?\\d{4}\\b)"), "[PHONE]"),
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"), "[EMAIL]"),
]


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        extra = getattr(record, "extra", None)
        if extra and isinstance(extra, dict):
            log_entry.update(extra)
        return json.dumps(log_entry, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development."""

    COLORS: dict[int, str] = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        base = f"{color}{record.levelname:<8}{self.RESET} {record.name}: {record.getMessage()}"
        if hasattr(record, "request_id"):
            base = f"[{record.request_id[:8]}] {base}"
        return base


def setup_logging() -> None:
    """Configure root logger with structured JSON (prod) or colored console (dev)."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Remove existing handlers to avoid duplication
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    if settings.environment == "production":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(logging.INFO)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter())
        handler.setLevel(logging.DEBUG)

    root.addHandler(handler)

    # Quiet noisy third-party loggers in production
    if settings.environment == "production":
        for name in ("uvicorn.access", "sqlalchemy.engine", "celery"):
            logging.getLogger(name).setLevel(logging.WARNING)


def mask_sensitive(data: Any, depth: int = 0) -> Any:
    """Recursively mask sensitive fields (phone, email, password) in log data."""
    if depth > 5:
        return data
    if isinstance(data, dict):
        return {
            k: (
                "***"
                if k.lower() in SENSITIVE_FIELDS
                else mask_sensitive(v, depth + 1)
            )
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive(item, depth + 1) for item in data]
    if isinstance(data, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            data = pattern.sub(replacement, data)
    return data


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request/response details: method, path, status, duration, user_id."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        logger = logging.getLogger("app.request")
        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "Unhandled exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "client": request.client.host if request.client else None,
                },
            )
            raise

        duration_ms = (time.monotonic() - start) * 1000
        extra: dict[str, Any] = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client": request.client.host if request.client else None,
        }
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            extra["user_id"] = str(user_id)

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(level, "%s %s -> %d (%.2fms)", request.method, request.url.path, response.status_code, duration_ms)

        return response


def _build_error_response(status_code: int, detail: str | list[Any], error_type: str = "error") -> JSONResponse:
    # Ensure detail is always JSON-serializable (Pydantic errors may contain raw exceptions)
    if isinstance(detail, str):
        safe_detail = detail
        safe_details = None
    else:
        safe_detail = str(detail)
        try:
            safe_details = [{"msg": str(e.get("msg", "")), "loc": e.get("loc", [])} for e in detail if isinstance(e, dict)]
        except Exception:
            safe_details = None
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": error_type,
                "message": safe_detail,
                "details": safe_details,
            }
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logging.getLogger("app.error").warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _build_error_response(422, exc.errors(), "validation_error")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logging.getLogger("app.error").warning(
        "HTTP %d on %s %s: %s",
        exc.status_code,
        request.method,
        request.url.path,
        exc.detail,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _build_error_response(exc.status_code, exc.detail, "http_error")


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("app.error").exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _build_error_response(500, "Internal server error", "internal_error")


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
