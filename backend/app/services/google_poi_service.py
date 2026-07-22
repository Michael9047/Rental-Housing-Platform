# Google Maps POI 全量检索服务
# 移植自 frontend/public/poi-compare.html 的三路径搜索逻辑
# 路径A: 小贩中心（单矩形 searchText + includedType 过滤）
# 路径B: 高密度关键词（2×2 网格 searchText + 翻页）
# 路径C: 低密度关键词（searchNearby 圆形）
import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import TypeAlias

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ==================== 常量 ====================

# 母类→子类分组
CATEGORIES: dict[str, list[str]] = {
    "交通": ["地铁站", "公交站"],
    "医疗": ["医院", "药店"],
    "购物": ["超市", "便利店", "商场", "酒吧"],
    "美食": ["餐厅", "cafe", "烘焙", "快餐", "食阁"],
    "生活": ["市场", "健身房"],
    "地标": ["小贩中心"],
}

KW_ORDER: list[str] = [
    "地铁站", "公交站", "医院", "药店", "超市", "便利店", "商场", "酒吧",
    "餐厅", "cafe", "烘焙", "快餐", "食阁", "小贩中心", "市场", "健身房",
]

# searchNearby includedTypes（仅低密度结构化类型 + 小贩中心标记）
GM_NS: dict[str, list[str]] = {
    "地铁站": ["subway_station"],
    "商场": ["shopping_mall"],
    "医院": ["hospital"],
    "小贩中心": [],  # 空数组标记——走路径A特殊处理
}

# searchText 英文搜索词（数组=双词取并集）
GM_ST: dict[str, str | list[str]] = {
    "餐厅": "restaurant",
    "cafe": "cafe",
    "烘焙": "bakery",
    "快餐": "fast food",
    "食阁": "food centre",
    "超市": "supermarket",
    "便利店": "convenience store",
    "药店": "pharmacy",
    "健身房": "gym",
    "公交站": ["bus stop", "bus station"],
    "市场": "market",
    "酒吧": "bar",
}

# 翻页数: L1 美食 3 页, 其余 2 页
ST_PAGES: dict[str, int] = {
    "餐厅": 3, "cafe": 3, "烘焙": 3, "快餐": 3, "食阁": 3,
    "超市": 2, "便利店": 2, "药店": 2, "健身房": 2,
    "公交站": 2, "市场": 2, "酒吧": 2,
}

# 关键词颜色（与前端一致）
KW_COLORS: dict[str, str] = {
    "餐厅": "#a855f7", "cafe": "#92400e", "烘焙": "#ea580c", "快餐": "#dc2626",
    "食阁": "#0d9488", "地铁站": "#6366f1", "公交站": "#3b82f6", "医院": "#ef4444",
    "药店": "#22c55e", "超市": "#f59e0b", "便利店": "#eab308", "商场": "#ec4899",
    "酒吧": "#c084fc", "市场": "#84cc16", "健身房": "#06b6d4", "小贩中心": "#14b8a6",
}

# proximity 去重阈值
PROXIMITY_DEDUP: dict[str, int] = {
    "医院": 200, "商场": 150, "市场": 150, "地铁站": 150, "公交站": 80,
}

# Google Places API (New) 端点
GM_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
GM_SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# FieldMask
GM_FIELDMASK_ST = "places.displayName,places.location,places.formattedAddress,places.rating,places.id,nextPageToken"
GM_FIELDMASK_NS = "places.id,places.displayName,places.location,places.formattedAddress,places.rating"

# 并发 & 超时
SEMAPHORE_LIMIT = 6
REQUEST_TIMEOUT = 15.0
PAGE_DELAY = 0.4  # 翻页间隔（秒）


# ==================== 数据模型 ====================

@dataclass
class POIItem:
    """单个 POI 条目"""
    name: str
    lat: float
    lng: float
    distance_m: int
    keyword: str
    vicinity: str | None = None
    rating: float | None = None
    place_id: str = ""
    transit_lines: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "distance_m": self.distance_m,
            "keyword": self.keyword,
            "vicinity": self.vicinity,
            "rating": self.rating,
            "place_id": self.place_id,
            "transit_lines": self.transit_lines,
        }


# ==================== 工具函数 ====================

def _hav_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 距离（米）"""
    R = 6_371_000
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _circle_to_rect(lat: float, lng: float, radius_m: float) -> dict:
    """圆心 + 半径 → 外接矩形"""
    d_lat = radius_m / 111_320
    d_lng = radius_m / (111_320 * math.cos(math.radians(lat)))
    return {
        "low": {"latitude": lat - d_lat, "longitude": lng - d_lng},
        "high": {"latitude": lat + d_lat, "longitude": lng + d_lng},
    }


def _split_rect(rect: dict, grid: int = 2) -> list[dict]:
    """矩形 → grid×grid 子格"""
    d_lat = (rect["high"]["latitude"] - rect["low"]["latitude"]) / grid
    d_lng = (rect["high"]["longitude"] - rect["low"]["longitude"]) / grid
    cells = []
    for r in range(grid):
        for c in range(grid):
            cells.append({
                "low": {
                    "latitude": rect["low"]["latitude"] + r * d_lat,
                    "longitude": rect["low"]["longitude"] + c * d_lng,
                },
                "high": {
                    "latitude": rect["low"]["latitude"] + (r + 1) * d_lat,
                    "longitude": rect["low"]["longitude"] + (c + 1) * d_lng,
                },
            })
    return cells


# ==================== 核心服务 ====================

class GooglePOIService:
    """Google Maps POI 全量检索服务"""

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.gm_api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ─── 入口 ───────────────────────────────────

    async def search_all(
        self, lat: float, lng: float, radius_m: int = 2000
    ) -> dict[str, list[dict]]:
        """搜索全部 16 个关键词，返回 {keyword: [POI dict, ...]}"""
        sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
        tasks = []
        for _cat, kws in CATEGORIES.items():
            for kw in kws:
                tasks.append(self._search_one(kw, lat, lng, radius_m, sem))
        results = await asyncio.gather(*tasks)
        result_map: dict[str, list[dict]] = {}
        for kw, pois in results:
            result_map[kw] = [p.to_dict() for p in pois]
        return result_map

    async def _search_one(
        self, kw: str, lat: float, lng: float, radius_m: int, sem: asyncio.Semaphore,
    ) -> tuple[str, list[POIItem]]:
        async with sem:
            # 路径A：小贩中心
            if kw == "小贩中心":
                pois = await self._search_hawker_centre(lat, lng, radius_m)
            # 路径B：searchText 网格
            elif kw in GM_ST:
                en = GM_ST[kw]
                queries = en if isinstance(en, list) else [en]
                max_pages = ST_PAGES.get(kw, 2)
                pois = await self._search_text_grid(lat, lng, queries, radius_m, max_pages)
            # 路径C：searchNearby
            elif kw in GM_NS:
                types = GM_NS[kw]
                pois = await self._search_nearby_circle(lat, lng, types, radius_m) if types else []
            else:
                pois = []
            return (kw, pois)

    # ─── 路径A：小贩中心 ──────────────────────

    async def _search_hawker_centre(
        self, lat: float, lng: float, radius_m: int,
    ) -> list[POIItem]:
        """单矩形 searchText + includedType:food_court 过滤，双词 × 3 页"""
        queries = ["hawker centre", "food centre"]
        rect = _circle_to_rect(lat, lng, radius_m)
        client = await self._get_client()
        seen: set[str] = set()
        all_pois: list[POIItem] = []

        for q in queries:
            pt = None
            pc = 0
            while pc < 3:
                body: dict = {
                    "textQuery": q,
                    "pageSize": 20,
                    "includedType": "food_court",
                    "locationRestriction": {"rectangle": rect},
                }
                if pt:
                    body["pageToken"] = pt
                try:
                    r = await client.post(
                        GM_SEARCH_TEXT_URL,
                        json=body,
                        headers={
                            "Content-Type": "application/json",
                            "X-Goog-Api-Key": self.api_key,
                            "X-Goog-FieldMask": GM_FIELDMASK_ST,
                        },
                    )
                    if r.status_code != 200:
                        logger.warning("小贩中心→%s: HTTP %s", q, r.status_code)
                        break
                    data = r.json()
                    ps = data.get("places") or []
                    pc += 1
                    for p in ps:
                        pid = p.get("id", "")
                        if pid in seen:
                            continue
                        seen.add(pid)
                        loc = p.get("location", {})
                        p_lat = loc.get("latitude")
                        p_lng = loc.get("longitude")
                        if p_lat is None or p_lng is None:
                            continue
                        all_pois.append(POIItem(
                            name=p.get("displayName", {}).get("text", q),
                            lat=p_lat, lng=p_lng,
                            distance_m=round(_hav_distance(lat, lng, p_lat, p_lng)),
                            keyword="小贩中心",
                            vicinity=p.get("formattedAddress", ""),
                            rating=p.get("rating"),
                            place_id=pid,
                        ))
                    pt = data.get("nextPageToken")
                    if pt:
                        await asyncio.sleep(PAGE_DELAY)
                    else:
                        break
                except Exception:
                    logger.exception("小贩中心→%s 请求异常", q)
                    break
        logger.info("小贩中心: %d results (单矩形×双词)", len(all_pois))
        return all_pois

    # ─── 路径B：searchText 2×2 网格 ─────────────

    async def _search_text_grid(
        self, lat: float, lng: float, queries: list[str],
        radius_m: int, max_pages: int,
    ) -> list[POIItem]:
        """2×2 网格 searchText + 翻页"""
        rect = _circle_to_rect(lat, lng, radius_m)
        cells = _split_rect(rect, 2)
        client = await self._get_client()
        seen: set[str] = set()
        all_pois: list[POIItem] = []

        for cell in cells:
            for q in queries:
                pt = None
                pc = 0
                while pc < max_pages:
                    body: dict = {
                        "textQuery": q,
                        "pageSize": 20,
                        "locationRestriction": {"rectangle": cell},
                    }
                    if pt:
                        body["pageToken"] = pt
                    try:
                        r = await client.post(
                            GM_SEARCH_TEXT_URL,
                            json=body,
                            headers={
                                "Content-Type": "application/json",
                                "X-Goog-Api-Key": self.api_key,
                                "X-Goog-FieldMask": GM_FIELDMASK_ST,
                            },
                        )
                        if r.status_code != 200:
                            txt = r.text[:200]
                            logger.warning("searchText %s: HTTP %s — %s", q, r.status_code, txt)
                            break
                        data = r.json()
                        ps = data.get("places") or []
                        pc += 1
                        for p in ps:
                            pid = p.get("id", "")
                            if pid in seen:
                                continue
                            seen.add(pid)
                            loc = p.get("location", {})
                            p_lat = loc.get("latitude")
                            p_lng = loc.get("longitude")
                            if p_lat is None or p_lng is None:
                                continue
                            all_pois.append(POIItem(
                                name=p.get("displayName", {}).get("text", q),
                                lat=p_lat, lng=p_lng,
                                distance_m=round(_hav_distance(lat, lng, p_lat, p_lng)),
                                keyword=q,  # 回填时替换为中文 key
                                vicinity=p.get("formattedAddress", ""),
                                rating=p.get("rating"),
                                place_id=pid,
                            ))
                        pt = data.get("nextPageToken")
                        if pt:
                            await asyncio.sleep(PAGE_DELAY)
                        else:
                            break
                    except Exception:
                        logger.exception("searchText %s 请求异常", q)
                        break
        # 回填正确的中文 keyword
        for p in all_pois:
            p.keyword = self._resolve_keyword(p.keyword)
        logger.info("searchText grid: %d results (%d 格 × %d 词)", len(all_pois), len(cells), len(queries))
        return all_pois

    # ─── 路径C：searchNearby 圆形 ───────────────

    async def _search_nearby_circle(
        self, lat: float, lng: float, included_types: list[str], radius_m: int,
    ) -> list[POIItem]:
        """searchNearby 圆形搜索"""
        client = await self._get_client()
        try:
            r = await client.post(
                GM_SEARCH_NEARBY_URL,
                json={
                    "includedTypes": included_types,
                    "maxResultCount": 20,
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": lat, "longitude": lng},
                            "radius": float(radius_m),
                        }
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": GM_FIELDMASK_NS,
                },
            )
            if r.status_code != 200:
                txt = r.text[:200]
                logger.warning("searchNearby %s: HTTP %s — %s", included_types, r.status_code, txt)
                return []
            data = r.json()
            ps = data.get("places") or []
            pois: list[POIItem] = []
            for p in ps:
                loc = p.get("location", {})
                p_lat = loc.get("latitude")
                p_lng = loc.get("longitude")
                if p_lat is None or p_lng is None:
                    continue
                pois.append(POIItem(
                    name=p.get("displayName", {}).get("text", included_types[0]),
                    lat=p_lat, lng=p_lng,
                    distance_m=round(_hav_distance(lat, lng, p_lat, p_lng)),
                    keyword="",  # 回填
                    vicinity=p.get("formattedAddress", ""),
                    rating=p.get("rating"),
                    place_id=p.get("id", ""),
                ))
            # 回填 keyword
            for p in pois:
                p.keyword = self._resolve_nearby_keyword(included_types)
            logger.info("searchNearby %s: %d results", included_types, len(pois))
            return pois
        except Exception:
            logger.exception("searchNearby %s 请求异常", included_types)
            return []

    # ─── keyword 回填 ──────────────────────────

    @staticmethod
    def _resolve_keyword(query: str) -> str:
        """把英文搜索词映射回中文 keyword（searchText 路径用）"""
        mapping = {
            "restaurant": "餐厅", "cafe": "cafe", "bakery": "烘焙",
            "fast food": "快餐", "food centre": "食阁",
            "supermarket": "超市", "convenience store": "便利店",
            "pharmacy": "药店", "gym": "健身房",
            "bus stop": "公交站", "bus station": "公交站",
            "market": "市场", "bar": "酒吧",
        }
        return mapping.get(query, query)

    @staticmethod
    def _resolve_nearby_keyword(types: list[str]) -> str:
        """把 includedTypes 映射回中文 keyword（searchNearby 路径用）"""
        mapping = {
            "subway_station": "地铁站",
            "shopping_mall": "商场",
            "hospital": "医院",
        }
        for t in types:
            if t in mapping:
                return mapping[t]
        return types[0] if types else ""

    # ─── 去重（post-search）───────────────────

    @staticmethod
    def dedup_by_name(pois: list[POIItem], threshold_m: float = 50) -> list[POIItem]:
        """同名 + proximity 去重"""
        sorted_pois = sorted(pois, key=lambda p: p.distance_m)
        kept: list[POIItem] = []
        for p in sorted_pois:
            norm = "".join(c for c in p.name.lower() if c.isalnum())
            dup = any(
                "".join(c for c in k.name.lower() if c.isalnum()) == norm
                and _hav_distance(p.lat, p.lng, k.lat, k.lng) < threshold_m
                for k in kept
            )
            if not dup:
                kept.append(p)
        return kept

    @staticmethod
    def dedup_proximity(pois: list[POIItem], threshold_m: float) -> list[POIItem]:
        """纯 proximity 去重"""
        sorted_pois = sorted(pois, key=lambda p: p.distance_m)
        kept: list[POIItem] = []
        for p in sorted_pois:
            if not any(_hav_distance(p.lat, p.lng, k.lat, k.lng) < threshold_m for k in kept):
                kept.append(p)
        return kept

    def apply_all_dedup(self, result_map: dict[str, list[POIItem]]) -> dict[str, list[POIItem]]:
        """对所有关键词结果应用去重"""
        # proximity 去重
        for kw, threshold in PROXIMITY_DEDUP.items():
            if kw in result_map:
                result_map[kw] = self.dedup_proximity(result_map[kw], threshold)
        # 同名去重（所有 searchText 关键词）
        for kw in GM_ST:
            if kw in result_map:
                result_map[kw] = self.dedup_by_name(result_map[kw], 50)
        return result_map
