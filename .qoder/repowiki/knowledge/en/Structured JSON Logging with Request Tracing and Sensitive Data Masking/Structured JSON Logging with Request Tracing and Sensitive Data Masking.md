---
kind: logging_system
name: Structured JSON Logging with Request Tracing and Sensitive Data Masking
category: logging_system
scope:
    - '**'
source_files:
    - backend/app/core/logging.py
    - backend/app/main.py
---

The backend uses Python's built-in `logging` module configured through a dedicated `app/core/logging.py` module. The system provides structured JSON logging for production, colored console output for development, request/response correlation via `request_id`, and automatic masking of sensitive fields.

**Core Components:**
- `JsonFormatter`: Produces structured JSON log entries with timestamp (UTC), level, logger name, message, module, function, exception traceback, `request_id`, `user_id`, and any extra fields attached to the record.
- `ColoredFormatter`: Human-friendly colored console output for development, including short `request_id` prefix.
- `RequestLoggingMiddleware`: Starlette middleware that wraps every FastAPI request, attaches a UUID-based `request_id` to `request.state`, measures duration in milliseconds, logs method/path/status/duration/client, and elevates 4xx+ responses to WARNING level.
- `mask_sensitive()`: Recursively walks dicts/lists/strings to redact known sensitive field names (`password`, `phone`, `email`, `secret`, `token`, `authorization`, `cookie`) and match phone/email patterns before they reach the formatter.
- Global exception handlers: `validation_exception_handler`, `http_exception_handler`, `generic_exception_handler` — all use `logging.getLogger("app.error")` and attach the current `request_id` from `request.state`.

**Initialization & Wiring:**
- `setup_logging()` is called at app startup in `app/main.py::create_app()`. It sets root logger level to DEBUG when `settings.debug` is true, INFO otherwise, installs a single StreamHandler on stdout, and suppresses noisy third-party loggers (`uvicorn.access`, `sqlalchemy.engine`, `celery`) to WARNING in production.
- `RequestLoggingMiddleware` is added as an outer middleware so it captures all requests.
- `register_exception_handlers(app)` registers the three global handlers.

**Log Levels Strategy:**
- Development: root level DEBUG, colored console output.
- Production: root level INFO, JSON stdout, noisy subsystems downgraded to WARNING.
- Request-level: INFO for 2xx/3xx, WARNING for 4xx+, ERROR for unhandled exceptions.

**Structured Fields Emitted Per Request:**
`timestamp`, `level`, `logger`, `message`, `module`, `function`, `request_id`, `method`, `path`, `status_code`, `duration_ms`, `client`, optionally `user_id`, plus any `extra={}` dict merged into the record.

**Conventions for Developers:**
- Use `logging.getLogger("app.<area>")` (e.g. `app.request`, `app.error`) rather than the root logger.
- Attach contextual data via `extra={...}` on each call; these are merged into the JSON record by `JsonFormatter`.
- Do not pass raw secrets in messages or `extra`; rely on `mask_sensitive()` if you must include structured payloads, or avoid them entirely.
- Prefer `logger.info(...)` / `logger.warning(...)` / `logger.exception(...)` over `print()`.