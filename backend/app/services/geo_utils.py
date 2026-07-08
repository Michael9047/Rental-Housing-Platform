"""
地理空间工具 — 纯数学算法
- GeoHash 球面编码：经纬度 → 空间索引字符串
- Haversine 距离计算：两点间球面距离
- 周边 GeoHash 邻域计算：快速邻近房源检索
"""
import math
from decimal import Decimal

# GeoHash Base32 编码表
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BASE32_REVERSE = {c: i for i, c in enumerate(_BASE32)}

# 经度范围 [-180, 180]，纬度范围 [-90, 90]
_LNG_RANGE = (-180.0, 180.0)
_LAT_RANGE = (-90.0, 90.0)

# 邻域偏移（8 个方向 + 自身）
_NEIGHBORS_ODD: dict[str, list[tuple[float, float]]] = {
    "n": [(0, 1), (-1, 1), (1, 0)],
    "s": [(0, -1), (-1, 0), (1, 1)],
    "e": [(1, 0), (0, 1), (1, -1)],
    "w": [(-1, 0), (0, -1), (-1, 1)],
}


def geohash_encode(lat: float, lng: float, precision: int = 7) -> str:
    """
    GeoHash 编码：经纬度 → Base32 字符串

    原理：交替二分经度和纬度范围，每 5 次二分生成一个 Base32 字符

    参数:
        lat: 纬度 (-90 ~ 90)
        lng: 经度 (-180 ~ 180)
        precision: 精度（字符数），默认 7（约 150m × 150m）
    返回:
        GeoHash 字符串
    """
    if not (-90 <= lat <= 90):
        raise ValueError(f"纬度超出范围: {lat}")
    if not (-180 <= lng <= 180):
        raise ValueError(f"经度超出范围: {lng}")

    lat_min, lat_max = _LAT_RANGE
    lng_min, lng_max = _LNG_RANGE

    geohash = ""
    bit = 0
    char_idx = 0
    is_lng = True  # 交替编码，从经度开始

    while len(geohash) < precision:
        if is_lng:
            mid = (lng_min + lng_max) / 2
            if lng >= mid:
                char_idx |= (1 << (4 - bit))
                lng_min = mid
            else:
                lng_max = mid
        else:
            mid = (lat_min + lat_max) / 2
            if lat >= mid:
                char_idx |= (1 << (4 - bit))
                lat_min = mid
            else:
                lat_max = mid

        is_lng = not is_lng
        bit += 1

        if bit == 5:
            geohash += _BASE32[char_idx]
            bit = 0
            char_idx = 0

    return geohash


def geohash_decode(geohash: str) -> tuple[float, float, float, float]:
    """
    GeoHash 解码：Base32 字符串 → 经纬度边界框

    返回:
        (lat_min, lat_max, lng_min, lng_max)
    """
    lat_min, lat_max = _LAT_RANGE
    lng_min, lng_max = _LNG_RANGE
    is_lng = True

    for char in geohash:
        if char not in _BASE32_REVERSE:
            raise ValueError(f"无效字符: {char}")
        idx = _BASE32_REVERSE[char]
        for bit_pos in range(4, -1, -1):
            bit = (idx >> bit_pos) & 1
            if is_lng:
                mid = (lng_min + lng_max) / 2
                if bit == 1:
                    lng_min = mid
                else:
                    lng_max = mid
            else:
                mid = (lat_min + lat_max) / 2
                if bit == 1:
                    lat_min = mid
                else:
                    lat_max = mid
            is_lng = not is_lng

    return lat_min, lat_max, lng_min, lng_max


def geohash_center(geohash: str) -> tuple[float, float]:
    """返回 GeoHash 区域的中心坐标"""
    lat_min, lat_max, lng_min, lng_max = geohash_decode(geohash)
    return (lat_min + lat_max) / 2, (lng_min + lng_max) / 2


def hav_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Haversine 公式：计算两点间球面距离

    公式：
        a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlng/2)
        c = 2·atan2(√a, √(1−a))
        d = R·c

    参数:
        lat1, lng1: 点 1 的纬度和经度
        lat2, lng2: 点 2 的纬度和经度
    返回:
        距离，单位 公里 (km)
    """
    R = 6371.0  # 地球半径 (km)

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def hav_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 距离，单位 米"""
    return hav_distance(lat1, lng1, lat2, lng2) * 1000


def bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    计算从点 1 到点 2 的方位角（0°=北, 90°=东）

    返回:
        方位角，单位 度 (0~360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlng = math.radians(lng2 - lng1)

    x = math.sin(dlng) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad)
         - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlng))

    bearing_rad = math.atan2(x, y)
    bearing_deg = (math.degrees(bearing_rad) + 360) % 360
    return bearing_deg


def bearing_to_direction(bearing_deg: float) -> str:
    """方位角 → 中文方向"""
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    idx = round(bearing_deg / 45) % 8
    return directions[idx]


def is_within_radius(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
    radius_km: float,
) -> bool:
    """判断两点是否在指定半径内"""
    return hav_distance(lat1, lng1, lat2, lng2) <= radius_km


def calculate_distance_to_pois(
    property_lat: float,
    property_lng: float,
    pois: list[dict],
) -> list[dict]:
    """
    计算房源到多个 POI 的距离

    参数:
        property_lat/lng: 房源坐标
        pois: POI 列表，每个需含 "name", "lat", "lng"
    返回:
        按距离排序的 POI 列表，附加 "distance_km" 和 "direction" 字段
    """
    results = []
    for poi in pois:
        dist = hav_distance(
            property_lat, property_lng,
            float(poi["lat"]), float(poi["lng"]),
        )
        b = bearing(
            property_lat, property_lng,
            float(poi["lat"]), float(poi["lng"]),
        )
        results.append({
            **poi,
            "distance_km": round(dist, 2),
            "distance_m": round(dist * 1000),
            "direction": bearing_to_direction(b),
        })
    results.sort(key=lambda x: x["distance_km"])
    return results


# ── 预设地标（留学生常用参考点）───────────────────────────

# 苏州各高校坐标（WGS84）
SUZHOU_UNIVERSITIES = {
    "西交利物浦大学": (31.2745, 120.7380),
    "苏州大学独墅湖校区": (31.2700, 120.7350),
    "苏州大学天赐庄校区": (31.3060, 120.6530),
    "苏州科技大学": (31.2880, 120.5850),
    "中国人民大学苏州校区": (31.2720, 120.7400),
    "SKEMA商学院苏州校区": (31.2730, 120.7390),
}

# 苏州主要商圈
SUZHOU_COMMERCIAL = {
    "苏州中心": (31.3180, 120.6780),
    "圆融时代广场": (31.3220, 120.7320),
    "观前街": (31.3090, 120.6280),
    "龙湖天街": (31.2950, 120.5600),
    "久光百货": (31.3200, 120.7300),
}


def calculate_distances_to_landmarks(
    lat: float, lng: float,
) -> dict[str, list[dict]]:
    """
    计算房源到所有预设地标的距离
    用于房源详情页展示"距离西交利物浦 X 公里"等信息
    """
    uni_results = calculate_distance_to_pois(
        lat, lng,
        [{"name": k, "lat": v[0], "lng": v[1]} for k, v in SUZHOU_UNIVERSITIES.items()],
    )
    comm_results = calculate_distance_to_pois(
        lat, lng,
        [{"name": k, "lat": v[0], "lng": v[1]} for k, v in SUZHOU_COMMERCIAL.items()],
    )
    return {
        "universities": uni_results[:3],   # 最近 3 所高校
        "commercial": comm_results[:3],     # 最近 3 个商圈
    }
