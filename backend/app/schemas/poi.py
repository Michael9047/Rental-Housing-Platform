from datetime import datetime

from pydantic import BaseModel, ConfigDict


class POIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: int
    content: str
    poi_data: dict | None = None
    generated_at: datetime
    reviewed: bool
    created_at: datetime
    updated_at: datetime


# ── 地图小卡片 POI ────────────────────────────────────────────

class MapPOIItem(BaseModel):
    """单个地图 POI 标记"""
    id: int | str
    name: str
    lat: float
    lng: float
    distance: int | None = None   # 米
    line: str | None = None       # 公交/地铁线路名


class MapPOIResponse(BaseModel):
    """房源地图 POI 预生成数据"""
    property_id: int
    generated_at: datetime | None = None
    search_radius_m: int = 3000
    categories: dict[str, list[MapPOIItem]]