import asyncio
import logging
from contextlib import suppress

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, register_exception_handlers, setup_logging
from app.core.security_audit import RateLimitMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.monitoring import PrometheusMiddleware, add_metrics_endpoint, install_celery_metrics


async def _run_local_notification_scheduler() -> None:
    """开发环境轻量提醒调度：无需单独启动 Celery beat，outbox 幂等键会阻止重复发送。"""
    from app.tasks.payment_tasks import (
        send_contract_expiring_12h_reminders,
        send_payment_expiring_3h_reminders,
    )

    while True:
        try:
            await asyncio.to_thread(send_payment_expiring_3h_reminders)
            await asyncio.to_thread(send_contract_expiring_12h_reminders)
        except Exception:
            logging.getLogger(__name__).exception("本地通知定时扫描失败")
        await asyncio.sleep(300)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        # 开发环境同样不能将本机路径和完整 traceback 返回给浏览器。
        debug=False,
        version="0.1.0",
    )

    if settings.environment.lower() != "production":
        @app.on_event("startup")
        async def start_local_notification_scheduler() -> None:
            app.state.local_notification_scheduler = asyncio.create_task(_run_local_notification_scheduler())

        @app.on_event("shutdown")
        async def stop_local_notification_scheduler() -> None:
            task = getattr(app.state, "local_notification_scheduler", None)
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    # CORS — relaxed in dev, tighten in prod via env
    # 不能用 ["*"] + allow_credentials=True，浏览器会直接拒绝
    cors_origins: list[str] = (
        settings.cors_origins
        if settings.environment == "production"
        else ["http://127.0.0.1:5173", "http://localhost:5173", "http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8012", "null"]
    )
    allow_creds = settings.environment == "production"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_creds,
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

    # 公开端点（必须在 include_router 之前注册，否则被 api_router 覆盖）
    @app.get("/api/v1/public/buildings")
    async def public_buildings(skip: int = 0, limit: int = 50):
        from app.db.session import async_session_maker
        from sqlalchemy import select as sa_select
        from sqlalchemy.orm import selectinload
        from app.models.institute import Institute, InstituteStatus
        async with async_session_maker() as session:
            stmt = (sa_select(Institute)
                    .options(selectinload(Institute.images))
                    .options(selectinload(Institute.unit_types))
                    .where(Institute.status == InstituteStatus.active)
                    .order_by(Institute.id.desc())
                    .offset(skip).limit(limit))
            result = await session.scalars(stmt)
            return [{
                "id": b.id, "name": b.name, "name_cn": b.name_cn, "address": b.address,
                "amenities": b.amenities,
                "female_only": bool(b.female_only) if b.female_only is not None else False,
                "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
                "unit_type_count": len(b.unit_types) if b.unit_types else 0,
                "primary_image": next(({"id": img.id, "filename": img.filename, "is_primary": img.is_primary}
                    for img in sorted(b.images or [], key=lambda x: x.sort_order)), None),
            } for b in result]

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Mount uploads directory for static file serving
    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/v1/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    # 开发工具：AGENT_TEST.html
    from fastapi.responses import FileResponse, HTMLResponse
    _TEST_HTML_PATH = Path(__file__).resolve().parent.parent / "test" / "AGENT_TEST.html"

    @app.get("/debug/routes", include_in_schema=False)
    async def debug_routes():
        """列出所有注册路由，诊断用。"""
        routes = []
        for r in app.routes:
            routes.append({"path": getattr(r, "path", str(r)), "methods": getattr(r, "methods", None)})
        return {"test_file_exists": _TEST_HTML_PATH.is_file(), "test_file_path": str(_TEST_HTML_PATH), "routes": [r for r in routes if "/test" in r["path"] or "/debug" in r["path"]]}

    @app.get("/test/agent", include_in_schema=False)
    async def agent_test_page():
        if not _TEST_HTML_PATH.is_file():
            return HTMLResponse("<h1>File not found: " + str(_TEST_HTML_PATH) + "</h1>", status_code=404)
        return FileResponse(str(_TEST_HTML_PATH))

    # 根路由 — 返回 API 基本信息（避免浏览器访问时 404 白屏）
    @app.get("/")
    async def root():
        return {
            "app": "Rental Housing Matching System",
            "version": "0.1.0",
            "docs": "/docs",
            "api_prefix": "/api/v1",
            "frontend": settings.frontend_url,
        }

    return app


app = create_app()
