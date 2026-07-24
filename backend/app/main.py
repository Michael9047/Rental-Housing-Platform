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


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    # CORS — relaxed in dev, tighten in prod via env
    # 不能用 ["*"] + allow_credentials=True，浏览器会直接拒绝
    cors_origins: list[str] = (
        settings.cors_origins
        if settings.environment == "production"
        else ["http://localhost:5173", "http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8012", "null"]
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

    # 临时直出端点 — 绕过 Pydantic schema 兼容问题
    @app.get("/api/v1/public/rooms/{room_id}")
    async def public_room_detail(room_id: int):
        from app.db.session import async_session_maker
        from sqlalchemy import select as sa_select, text
        async with async_session_maker() as session:
            r = await session.execute(text(
                "SELECT r.*, COALESCE(r.safety_score,0) as s_score FROM rooms r WHERE r.id = :id AND r.deleted_at IS NULL"
            ), {"id": room_id})
            row = r.first()
            if not row:
                from fastapi import HTTPException
                raise HTTPException(404, "Room not found")
            # Return as dict using column names
            cols = r.keys()
            return dict(zip(cols, row))

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Mount uploads directory for static file serving
    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/v1/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    # 根路由 — 返回 API 基本信息（避免浏览器访问时 404 白屏）
    @app.get("/")
    async def root():
        return {
            "app": "Rental Housing Matching System",
            "version": "0.1.0",
            "docs": "/docs",
            "api_prefix": "/api/v1",
            "frontend": "http://localhost:5173",
        }

    return app


app = create_app()
