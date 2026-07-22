# 新加坡 NPC 代码映射 + 边界匹配
# GeoJSON 来源: data.gov.sg NPC Boundary (d_89b44df21fccc4f51390eaff16aa1fe8)
import json
import math
import os
from functools import lru_cache

# ═══════════════════════════════════════════════════════
# GeoJSON 缩写 → 犯罪数据全名
# ═══════════════════════════════════════════════════════

NPC_CODE_MAP: dict[str, str] = {
    # Non-residential (no crime data, fall back to nearest)
    "M-Sect": "",   # Marina Bay sector
    "APD": "",      # Airport Police Division
    # Central Division
    "MB-NPC": "Central Police Division - Marina Bay NPC",
    "BE-NPC": "Central Police Division - Bukit Merah East NPC",
    "RC-NPC": "Central Police Division - Rochor NPC",
    # Clementi Division
    "CL-NPC": "Clementi Police Division - Clementi NPC",
    "QT-NPC": "Clementi Police Division - Queenstown NPC",
    "BM-NPC": "Clementi Police Division - Bukit Merah West NPC",
    "JE-NPC": "Clementi Police Division - Jurong East NPC",
    # Tanglin Division
    "BI-NPC": "Tanglin Police Division - Bishan NPC",
    "TY-NPC": "Tanglin Police Division - Toa Payoh NPC",
    "KJ-NPC": "Tanglin Police Division - Kampong Java NPC",
    "OR-NPC": "Tanglin Police Division - Orchard NPC",
    # Bedok Division
    "BD-NPC": "Bedok Police Division - Bedok NPC",
    "CG-NPC": "Bedok Police Division - Changi NPC",
    "GL-NPC": "Bedok Police Division - Geylang NPC",
    "MP-NPC": "Bedok Police Division - Marine Parade NPC",
    "PR-NPC": "Bedok Police Division - Pasir Ris NPC",
    "TP-NPC": "Bedok Police Division - Tampines NPC",
    # Ang Mo Kio Division
    "AN-NPC": "Ang Mo Kio Police Division - Ang Mo Kio North NPC",
    "AS-NPC": "Ang Mo Kio Police Division - Ang Mo Kio South NPC",
    "SG-NPC": "Ang Mo Kio Police Division - Sengkang NPC",
    "PG-NPC": "Ang Mo Kio Police Division - Punggol NPC",
    "WL-NPC": "Ang Mo Kio Police Division - Woodleigh NPC",
    # Jurong Division
    "JW-NPC": "Jurong Police Division - Jurong West NPC",
    "BK-NPC": "Jurong Police Division - Bukit Batok NPC",
    "CK-NPC": "Jurong Police Division - Choa Chu Kang NPC",
    "NY-NPC": "Jurong Police Division - Nanyang NPC",
    # Woodlands Division
    "SW-NPC": "Woodlands Police Division - Sembawang NPC",
    "WW-NPC": "Woodlands Police Division - Woodlands West NPC",
    "WE-NPC": "Woodlands Police Division - Woodlands East NPC",
    "YI-NPC": "Woodlands Police Division - Yishun North NPC",
}


# ═══════════════════════════════════════════════════════
# Point-in-Polygon (ray-casting algorithm)
# ═══════════════════════════════════════════════════════

def _point_in_polygon(lat: float, lng: float, polygon: list[list[float]]) -> bool:
    """光线投射算法判断点是否在多边形内。
    polygon: [[lng, lat], ...] — GeoJSON 坐标格式
    水平射线: y=lat, 检查与多边形边的交点
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]  # lng, lat
        xj, yj = polygon[j][0], polygon[j][1]  # lng, lat
        # 边跨越水平射线 y=lat
        if ((yi > lat) != (yj > lat)):
            # 计算交点 x 坐标
            x_intersect = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < x_intersect:
                inside = not inside
        j = i
    return inside


@lru_cache(maxsize=1)
def _load_geojson() -> dict:
    """加载 NPC 边界 GeoJSON"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sg_npc_boundary.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_npc_by_boundary(lat: float, lng: float) -> str | None:
    """通过 Point-in-Polygon 精确匹配 NPC 辖区。
    返回 GeoJSON 缩写代码（如 'CL-NPC'），不在任何辖区内返回 None。
    """
    gj = _load_geojson()
    for feature in gj.get("features", []):
        props = feature.get("properties", {})
        code = props.get("NPC_NAME", "")
        if not code:
            continue
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            for ring in geometry.get("coordinates", []):
                if _point_in_polygon(lat, lng, ring):
                    return code
        elif geometry.get("type") == "MultiPolygon":
            for polygon in geometry.get("coordinates", []):
                for ring in polygon:
                    if _point_in_polygon(lat, lng, ring):
                        return code
    return None
