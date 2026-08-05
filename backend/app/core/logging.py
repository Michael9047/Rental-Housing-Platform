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
from datetime import UTC, datetime
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
    import io
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    utf8_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    if settings.environment == "production":
        handler = logging.StreamHandler(utf8_stream)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(logging.INFO)
    else:
        handler = logging.StreamHandler(utf8_stream)
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


async def _record_runtime_event(request: Request, exc: Exception, status_code: int) -> None:
    try:
        from app.db.session import async_session_maker
        from app.models.runtime_event import RuntimeEvent

        tb = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
        location = f"{tb.filename}:{tb.lineno}" if tb else None
        request_id = getattr(request.state, "request_id", None)
        user_id = getattr(request.state, "user_id", None)
        event = RuntimeEvent(
            level="ERROR",
            event_type=type(exc).__name__,
            title=f"{request.method} {request.url.path} 运行异常",
            message=str(mask_sensitive(str(exc)))[:1000] if str(exc) else type(exc).__name__,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            request_id=request_id,
            user_id=int(user_id) if str(user_id or "").isdigit() else None,
            extra={
                "错误类型": type(exc).__name__,
                "接口路径": request.url.path,
                "请求方法": request.method,
                "请求编号": request_id,
                "代码位置": location,
            },
        )
        async with async_session_maker() as session:
            session.add(event)
            await session.commit()
    except Exception:
        logging.getLogger("app.error").debug("Failed to persist runtime event", exc_info=True)


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
    if isinstance(detail, str):
        safe_detail = detail
        safe_details = None
    elif isinstance(detail, list):
        # 验证错误列表 → 格式化为可读字符串
        parts: list[str] = []
        for e in detail:
            if isinstance(e, dict):
                loc = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
                parts.append(f"{loc}: {e.get('msg', '')}" if loc else str(e.get("msg", "")))
            else:
                parts.append(str(e))
        safe_detail = "; ".join(parts) if parts else str(detail)
        safe_details = [{"msg": str(d.get("msg", "")), "loc": d.get("loc", [])} for d in detail if isinstance(d, dict)]
    else:
        safe_detail = str(detail)
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
        "⚠ Validation: %s %s → %s",
        request.method,
        request.url.path,
        "; ".join(f"{'.'.join(str(p) for p in e['loc'] if p not in ('body','query','path'))}: {e['msg']}" for e in exc.errors()[:3]),
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _build_error_response(422, exc.errors(), "validation_error")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logging.getLogger("app.error").warning(
        "⚠ HTTP %d: %s %s → %s",
        exc.status_code,
        request.method,
        request.url.path,
        exc.detail,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    if exc.status_code >= 500:
        await _record_runtime_event(request, exc, exc.status_code)
    return _build_error_response(exc.status_code, exc.detail, "http_error")


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    msg = str(exc) if settings.debug else "Internal server error"
    error_type = type(exc).__name__

    # 开发环境：打印简洁的错误摘要到控制台
    if settings.debug:
        import os as _os
        _tb = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
        _loc = f"{_os.path.basename(_tb.filename)}:{_tb.lineno}" if _tb else "?"
        logging.getLogger("app.error").error(
            "❌ %s → %s: %s [%s]", request.method, request.url.path, msg, _loc
        )
    else:
        logging.getLogger("app.error").exception(
            "Unhandled exception on %s %s",
            request.method, request.url.path,
            extra={"request_id": getattr(request.state, "request_id", None)},
        )

    await _record_runtime_event(request, exc, 500)
    return _build_error_response(500, msg, error_type)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
