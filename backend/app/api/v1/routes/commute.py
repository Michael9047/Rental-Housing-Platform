"""通勤时间计算 API —— 四种交通模式的真实路线时间

POST /api/v1/commute/calculate
    请求体：{ origin_lat, origin_lng, destinations: [{id, lat, lng}, ...], country?, city? }
    返回：{ results: [{dest_id, dist_km, walk_min, bike_min, drive_min, transit_min, source}], source }

POST /api/v1/commute/route
    请求体：{ origin_lat, origin_lng, dest_lat, dest_lng, mode, country?, city? }
    返回：{ mode, dist_km, duration_min, segments: [{polyline, distance_m, duration_s, ...}], source }
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.commute_service import (
    BatchCommuteResult,
    CommuteDestination,
    RouteDetail,
    RouteSegment,
    calculate_commute_batch_resilient,
    get_route_detail,
)

router = APIRouter()


# ── 请求/响应 Schema ──────────────────────────────────────────────────


class DestItem(BaseModel):
    id: int | str = Field(..., description="房源 ID")
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    lng: float = Field(..., ge=-180, le=180, description="经度")


class CommuteCalculateRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90, description="起点纬度（学校）")
    origin_lng: float = Field(..., ge=-180, le=180, description="起点经度（学校）")
    destinations: list[DestItem] = Field(..., min_length=1, max_length=50, description="目标房源列表（最多 50 个）")
    country: str | None = Field(None, min_length=2, max_length=2, description="国家代码（CN=高德，其他=Google）")
    city: str | None = Field(None, max_length=64, description="城市名（高德公交模式需要，如'苏州'）")


class CommuteItem(BaseModel):
    dest_id: int | str
    dist_km: float
    walk_min: int
    bike_min: int
    drive_min: int
    transit_min: int
    source: str
    transit_verified: bool = False


class CommuteCalculateResponse(BaseModel):
    results: list[CommuteItem]
    source: str  # "amap_api" | "ors_api" | "haversine_fallback"


# ── 路由 ──────────────────────────────────────────────────────────────


@router.post("/calculate", response_model=CommuteCalculateResponse)
async def calculate_commute(body: CommuteCalculateRequest):
    """批量计算通勤时间

    弹性四级降级链：
    - 国内 → 高德 → ORS → Google → Haversine
    - 海外 → ORS → Google → 高德 → Haversine
    - 全部失败时降级为 Haversine 直线距离估算

    返回四种模式：walk_min（步行）、bike_min（骑行）、drive_min（驾车）、transit_min（公交地铁）
    """
    destinations = [
        CommuteDestination(dest_id=d.id, lat=d.lat, lng=d.lng)
        for d in body.destinations
    ]

    result: BatchCommuteResult = await calculate_commute_batch_resilient(
        origin_lat=body.origin_lat,
        origin_lng=body.origin_lng,
        destinations=destinations,
        country=body.country,
        city=body.city,
    )

    return CommuteCalculateResponse(
        results=[
            CommuteItem(
                dest_id=r.dest_id,
                dist_km=r.dist_km,
                walk_min=r.walk_min,
                bike_min=r.bike_min,
                drive_min=r.drive_min,
                transit_min=r.transit_min,
                source=r.source,
                transit_verified=r.transit_verified,
            )
            for r in result.results
        ],
        source=result.source,
    )


# ── 路线详情 Schema ────────────────────────────────────────────────────


class RouteDetailRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90, description="起点纬度（学校）")
    origin_lng: float = Field(..., ge=-180, le=180, description="起点经度（学校）")
    dest_lat: float = Field(..., ge=-90, le=90, description="终点纬度（房源）")
    dest_lng: float = Field(..., ge=-180, le=180, description="终点经度（房源）")
    mode: str = Field(..., pattern=r"^(walking|bicycling|driving|transit)$", description="交通模式")
    country: str | None = Field(None, min_length=2, max_length=2, description="国家代码")
    city: str | None = Field(None, max_length=64, description="城市名（高德公交模式需要）")


class RouteSegmentOut(BaseModel):
    polyline: list[list[float]] = Field(default_factory=list, description="[[lat, lng], ...]")
    distance_m: float
    duration_s: int
    line_name: str | None = None
    vehicle_type: str | None = None
    departure_stop: str | None = None
    arrival_stop: str | None = None
    num_stops: int | None = None


class RouteDetailResponse(BaseModel):
    mode: str
    dist_km: float
    duration_min: int
    segments: list[RouteSegmentOut]
    source: str


# ── 路线详情路由 ────────────────────────────────────────────────────────


@router.post("/route", response_model=RouteDetailResponse)
async def route_detail(body: RouteDetailRequest):
    """获取单条路线详情（含 polyline 和公交换乘信息）

    地图展示用——三种非公交模式返回单一 polyline 段；公交模式返回多段（步行+线路），
    每段标注线路名、站点名、站数，前端按段分色绘制。
    """
    detail: RouteDetail = await get_route_detail(
        origin_lat=body.origin_lat,
        origin_lng=body.origin_lng,
        dest_lat=body.dest_lat,
        dest_lng=body.dest_lng,
        mode=body.mode,
        country=body.country,
        city=body.city,
    )

    return RouteDetailResponse(
        mode=detail.mode,
        dist_km=detail.dist_km,
        duration_min=detail.duration_min,
        segments=[
            RouteSegmentOut(
                polyline=seg.polyline,
                distance_m=seg.distance_m,
                duration_s=seg.duration_s,
                line_name=seg.line_name,
                vehicle_type=seg.vehicle_type,
                departure_stop=seg.departure_stop,
                arrival_stop=seg.arrival_stop,
                num_stops=seg.num_stops,
            )
            for seg in detail.segments
        ],
        source=detail.source,
    )
