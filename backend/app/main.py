from fastapi.staticfiles import StaticFiles
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, register_exception_handlers, setup_logging
from app.core.security_audit import RateLimitMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.monitoring import PrometheusMiddleware, add_metrics_endpoint, install_celery_metrics


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    # CORS ¡ª relaxed in dev, tighten in prod via env
    cors_origins: list[str] = (
        settings.cors_origins
        if settings.environment == "production"
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus metrics middleware
    app.add_middleware(PrometheusMiddleware)

    # Rate limiting middleware (Redis-backed)
    try:
        from redis.asyncio import Redis as AsyncRedis
        redis_client = AsyncRedis.from_url(settings.redis_url, decode_responses=False)
        limiter = RateLimitMiddleware(redis_client)

        class RateLimitHTTPMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
                await limiter.check(request)
                return await call_next(request)

        app.add_middleware(RateLimitHTTPMiddleware)
    except Exception:
        pass

    # Request/response logging middleware (must be outer to capture all)
    app.add_middleware(RequestLoggingMiddleware)

    # Global exception handlers
    register_exception_handlers(app)

    # Prometheus /metrics endpoint
    add_metrics_endpoint(app)

    # Install Celery task metrics signals
    install_celery_metrics()

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Mount uploads directory for static file serving
    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/v1/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    return app


app = create_app()
