"""通勤时间计算服务 —— 多引擎路线规划

方案 A：接入高德/Google 路线规划 API，获取四种交通模式的真实通勤时间。
方案 B（后续）：自建 OSRM 路由引擎。

引擎选择：
- 中国大陆 (CN) → 高德地图 Directions API（步行/骑行/驾车/公交）
- 海外 → Google Maps Distance Matrix API（批量，四种模式）
- API 不可用时 → Haversine 直线距离估算作为兜底

调用方式：
- 高德：每个目的地每种模式一次 HTTP 调用（并发 asyncio.gather）
- Google：所有目的地合并到一次 Distance Matrix 调用（分模式，共 4 次调用）
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.geocoding_service import _is_amap_primary

logger = logging.getLogger(__name__)

# ── 数据类 ────────────────────────────────────────────────────────────


@dataclass
class CommuteDestination:
    """待计算通勤的目标房源"""
    dest_id: int | str
    lat: float
    lng: float


@dataclass
class CommuteResult:
    """单个房源的通勤时间结果"""
    dest_id: int | str
    dist_km: float
    walk_min: int
    bike_min: int
    drive_min: int
    transit_min: int
    source: str = "api"  # "api" | "haversine_fallback"


@dataclass
class BatchCommuteResult:
    """批量通勤计算结果"""
    results: list[CommuteResult] = field(default_factory=list)
    source: str = "api"


@dataclass
class RouteSegment:
    """一段路线——步行/骑行/驾车只有一个 segment；公交有多个（步行+地铁+步行...）"""
    polyline: list[list[float]]  # [[lat, lng], ...]
    distance_m: float
    duration_s: int
    line_name: str | None = None       # 公交专属：线路名
    vehicle_type: str | None = None    # "walking" | "subway" | "bus"
    departure_stop: str | None = None  # 上车站名
    arrival_stop: str | None = None    # 下车站名
    num_stops: int | None = None       # 途经站数


@dataclass
class RouteDetail:
    """单次路线详情"""
    mode: str
    dist_km: float
    duration_min: int
    segments: list[RouteSegment] = field(default_factory=list)
    source: str = "api"


# ── Haversine 兜底估算 ────────────────────────────────────────────────

# 各模式速度 (km/h)，与前端 estimateCommute() 保持一致
_WALK_SPEED = 5.0
_BIKE_SPEED = 15.0
_DRIVE_SPEED = 35.0
_TRANSIT_SPEED = 20.0
_DETOUR_FACTOR = 1.35  # 直线距离 → 道路距离的估算系数


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 球面距离 (km)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _haversine_estimate(lat1: float, lng1: float, lat2: float, lng2: float) -> CommuteResult:
    """Haversine 直线距离估算（API 不可用时的兜底方案）"""
    dist = _haversine_km(lat1, lng1, lat2, lng2)
    road = dist * _DETOUR_FACTOR
    return CommuteResult(
        dest_id=0,  # caller 会覆盖
        dist_km=round(dist, 2),
        walk_min=max(1, round(road / _WALK_SPEED * 60)),
        bike_min=max(1, round(road / _BIKE_SPEED * 60)),
        drive_min=max(1, round(road / _DRIVE_SPEED * 60)),
        transit_min=max(1, round(road / _TRANSIT_SPEED * 60)),
        source="haversine_fallback",
    )


# ── Polyline 解析工具 ──────────────────────────────────────────────────


def _amap_polyline_to_coords(polyline_str: str) -> list[list[float]]:
    """高德 polyline 字符串 → [[lat, lng], ...]

    高德格式："lng1,lat1;lng2,lat2;..."
    """
    coords: list[list[float]] = []
    for pair in polyline_str.split(";"):
        pair = pair.strip()
        if not pair or "," not in pair:
            continue
        parts = pair.split(",", 1)
        try:
            lng = float(parts[0])
            lat = float(parts[1])
            coords.append([lat, lng])
        except (ValueError, IndexError):
            continue
    return coords


def _decode_google_polyline(encoded: str) -> list[list[float]]:
    """Google 编码 polyline 字符串 → [[lat, lng], ...]

    Google Polyline 编码算法：
    https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    coords: list[list[float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)

    while index < length:
        # 解码纬度
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # 解码经度
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coords.append([lat / 1e5, lng / 1e5])

    return coords


def _amap_steps_to_polyline(steps: list[dict]) -> list[list[float]]:
    """从高德 steps 数组拼接完整 polyline

    每个 step 可能包含 'polyline' 字段（分号分隔的 "lng,lat" 字符串）。
    如无 polyline，回退为"从 step 末尾坐标取点"（精度较低但不影响展示）。
    """
    all_coords: list[list[float]] = []
    for step in steps:
        pl_str = step.get("polyline")
        if pl_str and isinstance(pl_str, str) and pl_str.strip():
            all_coords.extend(_amap_polyline_to_coords(pl_str))
    return all_coords


_ROUTE_MODE_AMAP = {
    "walking": "amap_direction_walking_url",
    "bicycling": "amap_direction_bicycling_url",
    "driving": "amap_direction_driving_url",
    "transit": "amap_direction_transit_url",
}

_ROUTE_MODE_GM = {
    "walking": "walking",
    "bicycling": "bicycling",
    "driving": "driving",
    "transit": "transit",
}


# ── 高德地图 Directions API ───────────────────────────────────────────


class AmapCommuteService:
    """高德地图路线规划 —— 适用于中国大陆"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def web_key(self) -> str:
        return self.settings.amap_web_key

    async def _call_amap_direction(
        self,
        client: httpx.AsyncClient,
        url: str,
        origin: str,
        destination: str,
        **extra_params,
    ) -> tuple[int, float] | None:
        """调用高德 direction API，返回 (duration_seconds, distance_meters) 或 None"""
        params: dict[str, str] = {
            "key": self.web_key,
            "origin": origin,
            "destination": destination,
        }
        params.update({k: str(v) for k, v in extra_params.items() if v is not None})

        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("高德 direction API 调用失败 (%s): %s", url, exc)
            return None

        if data.get("status") != "1":
            logger.debug("高德 direction API 返回错误 (%s): %s", url, data.get("info", ""))
            return None

        route = data.get("route", {})
        paths = route.get("paths") or []
        if not paths:
            return None

        path = paths[0]
        duration = int(path.get("duration", 0))
        distance = int(path.get("distance", 0))
        if duration <= 0:
            return None
        return duration, float(distance)

    async def get_one(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        city: str | None = None,
    ) -> CommuteResult:
        """计算从起点到一个目的地的四种模式通勤时间"""
        origin = f"{origin_lng},{origin_lat}"
        destination = f"{dest_lng},{dest_lat}"
        dist = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)

        timeout = httpx.Timeout(self.settings.amap_direction_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            walk, bike, drive, transit = await asyncio.gather(
                self._call_amap_direction(client, self.settings.amap_direction_walking_url, origin, destination),
                self._call_amap_direction(client, self.settings.amap_direction_bicycling_url, origin, destination),
                self._call_amap_direction(client, self.settings.amap_direction_driving_url, origin, destination,
                                          **{"strategy": "0"}),
                self._call_amap_direction(client, self.settings.amap_direction_transit_url, origin, destination,
                                          **{"city": city or "", "cityd": city or ""}),
                return_exceptions=True,
            )

        def _unwrap(task_result) -> tuple[int, float] | None:
            if isinstance(task_result, BaseException):
                return None
            return task_result

        w = _unwrap(walk)
        b = _unwrap(bike)
        d = _unwrap(drive)
        t = _unwrap(transit)

        # 判断是否全部成功（至少步行和驾车必须成功才认为 API 有效）
        if w is not None and d is not None:
            return CommuteResult(
                dest_id=0,
                dist_km=round(dist, 2),
                walk_min=max(1, round(w[0] / 60)),
                bike_min=max(1, round(b[0] / 60)) if b else max(1, round(dist * _DETOUR_FACTOR / _BIKE_SPEED * 60)),
                drive_min=max(1, round(d[0] / 60)),
                transit_min=max(1, round(t[0] / 60)) if t else max(1, round(dist * _DETOUR_FACTOR / _TRANSIT_SPEED * 60)),
                source="api",
            )

        # API 部分失败 → 全部降级为 Haversine
        return _haversine_estimate(origin_lat, origin_lng, dest_lat, dest_lng)

    async def _amap_direction_raw(self, url: str, origin: str, destination: str, **extra) -> dict | None:
        """调用高德 direction API，返回完整 JSON 或 None"""
        params: dict[str, str] = {
            "key": self.web_key,
            "origin": origin,
            "destination": destination,
        }
        params.update({k: str(v) for k, v in extra.items() if v is not None})
        timeout = httpx.Timeout(self.settings.amap_direction_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("status") != "1":
                logger.debug("高德 direction API 返回错误 (%s): %s", url, data.get("info", ""))
                return None
            return data
        except Exception as exc:
            logger.debug("高德 direction API 调用失败 (%s): %s", url, exc)
            return None

    async def get_route_detail(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str,
        city: str | None = None,
    ) -> RouteDetail:
        """获取从起点到终点的单模式详细路线（含 polyline，公交含换乘信息）"""
        origin = f"{origin_lng},{origin_lat}"
        destination = f"{dest_lng},{dest_lat}"
        dist = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)

        url_attr = _ROUTE_MODE_AMAP.get(mode)
        if not url_attr:
            return RouteDetail(mode=mode, dist_km=round(dist, 2), duration_min=0, segments=[], source="unsupported_mode")
        url = getattr(self.settings, url_attr)

        extra: dict[str, Any] = {}
        if mode == "driving":
            extra["strategy"] = "0"
        if mode == "transit" and city:
            extra["city"] = city
            extra["cityd"] = city

        data = await self._amap_direction_raw(url, origin, destination, **extra)
        if not data:
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        route = data.get("route", {})

        # ── 公交模式：解析 transits ──
        if mode == "transit":
            transits = route.get("transits") or []
            if not transits:
                return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)
            transit = transits[0]
            segments_data = transit.get("segments") or []
            total_duration = int(transit.get("cost", {}).get("duration", transit.get("duration", 0)) or 0)
            if not total_duration:
                total_duration = sum(int(s.get("walking", {}).get("duration", 0) or 0) for s in segments_data)
                total_duration += sum(
                    int((bl.get("duration") or 0)) for s in segments_data
                    for bus in (s.get("bus", {}).get("buslines") or [])
                    if isinstance(bus, dict)
                )

            segments: list[RouteSegment] = []
            for seg in segments_data:
                walking = seg.get("walking") or {}
                walk_steps = walking.get("steps") or []
                walk_poly = _amap_steps_to_polyline(walk_steps)
                walk_dist = float(walking.get("distance", 0) or 0)
                walk_dur = int(walking.get("duration", 0) or 0)
                if walk_poly and walk_dist > 0:
                    segments.append(RouteSegment(
                        polyline=walk_poly, distance_m=walk_dist, duration_s=walk_dur,
                        vehicle_type="walking",
                    ))

                bus_info = seg.get("bus") or {}
                buslines = bus_info.get("buslines") or []
                for bl in buslines:
                    if not isinstance(bl, dict):
                        continue
                    bl_name = str(bl.get("name") or "")
                    bl_type = str(bl.get("type") or "bus")
                    dep_stop = (bl.get("departure_stop") or {}).get("name") if isinstance(bl.get("departure_stop"), dict) else None
                    arr_stop = (bl.get("arrival_stop") or {}).get("name") if isinstance(bl.get("arrival_stop"), dict) else None
                    via = int(bl.get("via_stops") or bl.get("via_num") or 0)
                    bl_dist = float(bl.get("distance", 0) or 0)
                    bl_dur = int(bl.get("duration", 0) or 0)

                    # 公交段 polyline：从 buslines 的 steps 或直接无 polyline
                    bl_steps = bl.get("steps") or []
                    bl_poly = _amap_steps_to_polyline(bl_steps)
                    if not bl_poly:
                        bl_poly = []

                    segments.append(RouteSegment(
                        polyline=bl_poly, distance_m=bl_dist, duration_s=bl_dur,
                        line_name=bl_name if bl_name else None,
                        vehicle_type="subway" if bl_type == "subway" else "bus",
                        departure_stop=dep_stop,
                        arrival_stop=arr_stop,
                        num_stops=via if via > 0 else None,
                    ))

            if not segments:
                return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

            return RouteDetail(
                mode=mode, dist_km=round(dist, 2),
                duration_min=max(1, round(total_duration / 60)),
                segments=segments, source="api",
            )

        # ── 步行/骑行/驾车：单 segment ──
        paths = route.get("paths") or []
        if not paths:
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        path = paths[0]
        steps = path.get("steps") or []
        polyline = _amap_steps_to_polyline(steps)
        total_dist = float(path.get("distance", 0) or 0)
        total_dur = int(path.get("duration", 0) or 0)

        if not polyline or total_dur <= 0:
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        return RouteDetail(
            mode=mode, dist_km=round(dist, 2),
            duration_min=max(1, round(total_dur / 60)),
            segments=[RouteSegment(
                polyline=polyline, distance_m=total_dist, duration_s=total_dur,
            )],
            source="api",
        )


# ── Google Maps Distance Matrix API ───────────────────────────────────

# Google Maps 模式映射
_GM_MODE_MAP = {
    "walk": "walking",
    "bike": "bicycling",
    "drive": "driving",
    "transit": "transit",
}


class GoogleCommuteService:
    """Google Maps Distance Matrix —— 适用于海外"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def api_key(self) -> str:
        return self.settings.gm_api_key

    async def _call_distance_matrix(
        self,
        client: httpx.AsyncClient,
        origin: str,
        destinations: str,
        mode: str,
    ) -> list[tuple[int, float] | None]:
        """调用 Google Distance Matrix API，返回 [(duration_s, distance_m), ...]"""
        params = {
            "key": self.api_key,
            "origins": origin,
            "destinations": destinations,
            "mode": mode,
        }
        try:
            resp = await client.get(self.settings.gm_distance_matrix_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Google Distance Matrix API 调用失败 (mode=%s): %s", mode, exc)
            return []

        if data.get("status") != "OK":
            logger.debug("Google Distance Matrix API 返回错误 (mode=%s): %s", mode, data.get("status", ""))
            return []

        results: list[tuple[int, float] | None] = []
        for row in data.get("rows", []):
            for element in row.get("elements", []):
                if element.get("status") == "OK":
                    duration_s = element.get("duration", {}).get("value", 0)
                    distance_m = element.get("distance", {}).get("value", 0)
                    if duration_s > 0:
                        results.append((duration_s, float(distance_m)))
                    else:
                        results.append(None)
                else:
                    results.append(None)
        return results

    async def get_batch(
        self,
        origin_lat: float,
        origin_lng: float,
        destinations: list[CommuteDestination],
    ) -> list[CommuteResult]:
        """批量计算从起点到多个目的地的四种模式通勤时间"""
        if not destinations:
            return []

        n = len(destinations)
        origin_str = f"{origin_lat},{origin_lng}"
        dests_str = "|".join(f"{d.lat},{d.lng}" for d in destinations)

        timeout = httpx.Timeout(self.settings.gm_direction_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            walk_r, bike_r, drive_r, transit_r = await asyncio.gather(
                self._call_distance_matrix(client, origin_str, dests_str, _GM_MODE_MAP["walk"]),
                self._call_distance_matrix(client, origin_str, dests_str, _GM_MODE_MAP["bike"]),
                self._call_distance_matrix(client, origin_str, dests_str, _GM_MODE_MAP["drive"]),
                self._call_distance_matrix(client, origin_str, dests_str, _GM_MODE_MAP["transit"]),
                return_exceptions=True,
            )

        def _unwrap(task_result) -> list:
            if isinstance(task_result, BaseException):
                return []
            return task_result or []

        walk = _unwrap(walk_r)
        bike = _unwrap(bike_r)
        drive = _unwrap(drive_r)
        transit = _unwrap(transit_r)

        results: list[CommuteResult] = []
        for i, dest in enumerate(destinations):
            dist = _haversine_km(origin_lat, origin_lng, dest.lat, dest.lng)

            w = walk[i] if i < len(walk) else None
            d = drive[i] if i < len(drive) else None

            if w is not None and d is not None:
                b = bike[i] if i < len(bike) else None
                t = transit[i] if i < len(transit) else None
                results.append(CommuteResult(
                    dest_id=dest.dest_id,
                    dist_km=round(dist, 2),
                    walk_min=max(1, round(w[0] / 60)),
                    bike_min=max(1, round(b[0] / 60)) if b else max(1, round(dist * _DETOUR_FACTOR / _BIKE_SPEED * 60)),
                    drive_min=max(1, round(d[0] / 60)),
                    transit_min=max(1, round(t[0] / 60)) if t else max(1, round(dist * _DETOUR_FACTOR / _TRANSIT_SPEED * 60)),
                    source="api",
                ))
            else:
                # Google API 部分失败 → Haversine 兜底
                fallback = _haversine_estimate(origin_lat, origin_lng, dest.lat, dest.lng)
                fallback.dest_id = dest.dest_id
                results.append(fallback)

        return results

    async def get_route_detail(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str,
    ) -> RouteDetail:
        """获取从起点到终点的单模式详细路线（调用 Google Directions API）"""
        dist = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
        gm_mode = _ROUTE_MODE_GM.get(mode)
        if not gm_mode:
            return RouteDetail(mode=mode, dist_km=round(dist, 2), duration_min=0, segments=[], source="unsupported_mode")

        params = {
            "key": self.api_key,
            "origin": f"{origin_lat},{origin_lng}",
            "destination": f"{dest_lat},{dest_lng}",
            "mode": gm_mode,
            "alternatives": "false",
        }
        if mode == "transit":
            params["transit_mode"] = "bus|subway|train|tram"

        timeout = httpx.Timeout(self.settings.gm_direction_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(self.settings.gm_directions_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.debug("Google Directions API 调用失败 (mode=%s): %s", mode, exc)
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        if data.get("status") != "OK":
            logger.debug("Google Directions API 返回错误 (mode=%s): %s", mode, data.get("status", ""))
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        routes = data.get("routes") or []
        if not routes:
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        route = routes[0]
        legs = route.get("legs") or []
        if not legs:
            return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        leg = legs[0]
        total_dist_m = float(leg.get("distance", {}).get("value", 0) or 0)
        total_dur_s = int(leg.get("duration", {}).get("value", 0) or 0)

        # ── 公交模式：按 step 分段 ──
        steps = leg.get("steps") or []
        if mode == "transit":
            segments: list[RouteSegment] = []
            for step in steps:
                td = step.get("transit_details")
                if td:
                    line_info = td.get("line") or {}
                    line_name = line_info.get("short_name") or line_info.get("name") or ""
                    vehicle_info = line_info.get("vehicle") or {}
                    vehicle_type = str(vehicle_info.get("type", "bus")).lower()
                    dep_stop = (td.get("departure_stop") or {}).get("name")
                    arr_stop = (td.get("arrival_stop") or {}).get("name")
                    num_stops = int(td.get("num_stops", 0) or 0)
                else:
                    line_name = None
                    vehicle_type = "walking"
                    dep_stop = None
                    arr_stop = None
                    num_stops = None

                # Decode step polyline
                encoded = step.get("polyline", {}).get("points", "")
                step_poly = _decode_google_polyline(encoded) if encoded else []

                step_dist = float(step.get("distance", {}).get("value", 0) or 0)
                step_dur = int(step.get("duration", {}).get("value", 0) or 0)

                segments.append(RouteSegment(
                    polyline=step_poly, distance_m=step_dist, duration_s=step_dur,
                    line_name=line_name,
                    vehicle_type=vehicle_type,
                    departure_stop=dep_stop,
                    arrival_stop=arr_stop,
                    num_stops=num_stops if num_stops > 0 else None,
                ))

            return RouteDetail(
                mode=mode, dist_km=round(dist, 2),
                duration_min=max(1, round(total_dur_s / 60)),
                segments=segments, source="api",
            )

        # ── 步行/骑行/驾车：单 segment ──
        encoded_poly = route.get("overview_polyline", {}).get("points", "")
        polyline = _decode_google_polyline(encoded_poly) if encoded_poly else []

        return RouteDetail(
            mode=mode, dist_km=round(dist, 2),
            duration_min=max(1, round(total_dur_s / 60)),
            segments=[RouteSegment(
                polyline=polyline, distance_m=total_dist_m, duration_s=total_dur_s,
            )],
            source="api",
        )


# ── 工厂 & 公共接口 ───────────────────────────────────────────────────


def get_commute_service(country: str | None = None):
    """根据国家代码返回对应的通勤计算服务"""
    if _is_amap_primary(country):
        return AmapCommuteService()
    return GoogleCommuteService()


async def calculate_commute_batch(
    origin_lat: float,
    origin_lng: float,
    destinations: list[CommuteDestination],
    country: str | None = None,
    city: str | None = None,
) -> BatchCommuteResult:
    """批量计算通勤时间 —— 公共入口

    Args:
        origin_lat/lng: 起点坐标（学校）
        destinations: 目标房源列表
        country: 国家代码（决定用高德还是 Google）
        city: 城市名（高德公交模式需要，中文名如"苏州"）

    Returns:
        BatchCommuteResult，其中 source 表示数据来源
    """
    if not destinations:
        return BatchCommuteResult(source="api")

    try:
        if _is_amap_primary(country):
            service = AmapCommuteService()
            if not service.web_key:
                logger.warning("高德 Web Key 未配置，降级为 Haversine 估算")
                return _fallback_batch(origin_lat, origin_lng, destinations)

            # 高德：逐个目的地并发计算（每个目的地 4 次 API 调用）
            tasks = [
                service.get_one(origin_lat, origin_lng, d.lat, d.lng, city=city)
                for d in destinations
            ]
            raw = await asyncio.gather(*tasks, return_exceptions=True)
            results: list[CommuteResult] = []
            api_ok = False
            for i, r in enumerate(raw):
                if isinstance(r, BaseException):
                    fb = _haversine_estimate(origin_lat, origin_lng, destinations[i].lat, destinations[i].lng)
                    fb.dest_id = destinations[i].dest_id
                    results.append(fb)
                else:
                    r.dest_id = destinations[i].dest_id
                    results.append(r)
                    if r.source == "api":
                        api_ok = True
            return BatchCommuteResult(
                results=results,
                source="api" if api_ok else "haversine_fallback",
            )
        else:
            service = GoogleCommuteService()
            if not service.api_key:
                logger.warning("Google Maps API Key 未配置，降级为 Haversine 估算")
                return _fallback_batch(origin_lat, origin_lng, destinations)

            results = await service.get_batch(origin_lat, origin_lng, destinations)
            return BatchCommuteResult(
                results=results,
                source=results[0].source if results else "api",
            )
    except Exception:
        logger.exception("通勤计算异常，降级为 Haversine 估算")
        return _fallback_batch(origin_lat, origin_lng, destinations)


def _fallback_batch(
    origin_lat: float,
    origin_lng: float,
    destinations: list[CommuteDestination],
) -> BatchCommuteResult:
    """全部降级为 Haversine 估算"""
    results = []
    for d in destinations:
        r = _haversine_estimate(origin_lat, origin_lng, d.lat, d.lng)
        r.dest_id = d.dest_id
        results.append(r)
    return BatchCommuteResult(results=results, source="haversine_fallback")


def _route_fallback(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    mode: str,
) -> RouteDetail:
    """路线详情降级——用直线作为 polyline"""
    dist = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    road = dist * _DETOUR_FACTOR
    speed = {"walking": _WALK_SPEED, "bicycling": _BIKE_SPEED, "driving": _DRIVE_SPEED, "transit": _TRANSIT_SPEED}.get(mode, _WALK_SPEED)
    dur = max(1, round(road / speed * 60))
    return RouteDetail(
        mode=mode, dist_km=round(dist, 2), duration_min=dur,
        segments=[RouteSegment(
            polyline=[[origin_lat, origin_lng], [dest_lat, dest_lng]],
            distance_m=road * 1000, duration_s=dur * 60,
        )],
        source="haversine_fallback",
    )


async def get_route_detail(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    mode: str,
    country: str | None = None,
    city: str | None = None,
) -> RouteDetail:
    """获取单条路线详情——公共入口

    Args:
        origin_lat/lng: 起点坐标（学校）
        dest_lat/lng: 终点坐标（房源）
        mode: "walking" | "bicycling" | "driving" | "transit"
        country: 国家代码
        city: 城市名（高德公交需要）
    """
    valid_modes = {"walking", "bicycling", "driving", "transit"}
    if mode not in valid_modes:
        return RouteDetail(mode=mode, dist_km=0, duration_min=0, segments=[], source="invalid_mode")

    try:
        if _is_amap_primary(country):
            service = AmapCommuteService()
            if not service.web_key:
                return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)
            return await service.get_route_detail(origin_lat, origin_lng, dest_lat, dest_lng, mode, city=city)
        else:
            service = GoogleCommuteService()
            if not service.api_key:
                return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)
            return await service.get_route_detail(origin_lat, origin_lng, dest_lat, dest_lng, mode)
    except Exception:
        logger.exception("路线详情获取异常，降级为直线")
        return _route_fallback(origin_lat, origin_lng, dest_lat, dest_lng, mode)
