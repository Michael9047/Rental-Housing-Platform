---
kind: error_handling
name: FastAPI Global Exception Handling with Structured JSON Error Responses
category: error_handling
scope:
    - '**'
source_files:
    - backend/app/core/logging.py
    - backend/app/main.py
    - backend/app/api/deps.py
    - backend/app/api/v1/routes/auth.py
    - backend/app/api/v1/routes/admin.py
    - backend/app/api/v1/routes/ai_search.py
---

The backend uses a centralized error-handling approach built on FastAPI's exception handler system, combined with structured logging and middleware-based request tracing. There is no custom domain-specific `Error` class hierarchy; instead, the codebase relies on FastAPI's `HTTPException` for business errors and a global `Exception` handler as a safety net.

**Global exception handlers** are registered in `app/core/logging.py` via `register_exception_handlers(app)` (called from `app/main.py`). Three handlers cover all cases:
- `validation_exception_handler`: converts Pydantic `RequestValidationError` into a uniform `{error: {type, message, details}}` JSON body with status 422.
- `http_exception_handler`: catches `StarletteHTTPException` (i.e., `fastapi.HTTPException`) and returns the same envelope with the original status code.
- `generic_exception_handler`: catches any unhandled `Exception`, logs it at `ERROR` level with full traceback, and returns status 500.

All three responses go through `_build_error_response`, which guarantees the response is always serializable by coercing non-string `detail` values and extracting only safe fields from Pydantic error dicts.

**Structured logging** is provided by `RequestLoggingMiddleware`, which wraps every request with a UUID `request_id`, records method/path/status/duration/user_id, and logs 4xx responses at WARNING level and 5xx at ERROR level. Sensitive fields (`password`, `phone`, `email`, `token`, etc.) are masked recursively before being logged.

**Route-level error propagation** follows a consistent pattern:
- Business failures raise `HTTPException` directly in route handlers or dependency functions (e.g., `deps.get_current_user`, `require_admin`, `auth.register_user` mapping `IntegrityError` to 409).
- Service-layer methods return `None` or Python exceptions rather than raising HTTP errors — routes translate them to `HTTPException`. For example, `AuthService.authenticate` returns `None` on bad credentials, and the auth route raises 401.
- External-service calls (AI search, payments) catch `RuntimeError`/`Exception` and re-raise as 503/502 `HTTPException`.

**No custom sentinel errors or typed error classes exist.** The codebase does not define an `AppError` / `ErrorCode` enum or a base `BusinessException`; role checks, validation, and resource-not-found cases are expressed purely via `HTTPException(status_code=..., detail=...)`.

**Frontend handling** (Vue services in `frontend/src/services/*.ts`) expects the `{error: {type, message, details}}` envelope returned by the global handlers and surfaces it to components via Axios interceptors or try/catch blocks. The WeChat miniprogram (`wechat-miniprogram/utils/api.js`) similarly inspects response codes and maps them to user-facing messages.