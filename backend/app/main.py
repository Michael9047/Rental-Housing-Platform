from fastapi.staticfiles import StaticFiles
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, register_exception_handlers, setup_logging
from app.core.monitoring import PrometheusMiddleware, add_metrics_endpoint, install_celery_metrics


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    # CORS — relaxed in dev, tighten in prod via env
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
