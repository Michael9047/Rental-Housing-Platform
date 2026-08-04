"""公寓 Pydantic 模式 — 结构化地址 + 经纬度校验"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


# 支持的国家列表
SUPPORTED_COUNTRIES = [
    "中国", "英国", "美国", "澳大利亚", "加拿大", "新加坡",
    "日本", "韩国", "法国", "德国", "马来西亚", "泰国",
]


def _compose_address(country: str | None, city: str | None, district: str | None, street: str | None) -> str | None:
    """由结构化字段拼接完整地址；任意字段为空则跳过"""
    parts = [p.strip() for p in [street, district, city, country] if p and p.strip()]
    return "，".join(parts) if parts else None


class InstituteCreate(BaseModel):
    """创建公寓 — 结构化地址，经纬度可选但前端会强制定位"""
    name: str = Field(..., min_length=1, max_length=200, description="公寓名称")
    name_cn: str | None = Field(default=None, max_length=200, description="中文名")
    abbreviation: str | None = Field(default=None, max_length=50, description="简称")

    # 结构化地址（推荐使用，也可直接传 address 兼容旧接口）
    country: str | None = Field(default=None, max_length=100, description="国家")
    city: str | None = Field(default=None, max_length=100, description="城市")
    district: str | None = Field(default=None, max_length=100, description="区/区域")
    street: str | None = Field(default=None, max_length=200, description="街道+门牌号")
    postal_code: str | None = Field(default=None, max_length=20, description="邮编")
    # 兼容旧接口：直接传完整地址
    address: str | None = Field(default=None, max_length=300, description="完整地址（兼容旧接口）")

    latitude: Decimal | None = Field(default=None, ge=-90, le=90, description="纬度")
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, description="经度")

    # 联系方式
    contact_phone: str | None = Field(default=None, max_length=32)
    contact_email: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500, description="公寓官网")

    # 建筑属性
    building_type: str | None = Field(default=None, max_length=50, description="dormitory/apartment/high-rise/low-rise")
    total_floors: int | None = Field(default=None, ge=0, description="总楼层")
    year_built: int | None = Field(default=None, ge=1800, description="建成年份")
    total_units: int | None = Field(default=None, ge=0, description="总单元数")
    has_elevator: bool = Field(default=False, description="有无电梯")

    # NPC 辖区
    npc: str | None = Field(default=None, max_length=100, description="新加坡 NPC 辖区简称")

    description: str | None = Field(default=None, max_length=5000)

    # 功能标记
    amenities: list[str] | None = Field(default=None)
    female_only: bool = False
    couples_allowed: bool = False

    # 负责人（保存时同步到 building_staff）
    manager_name: str | None = Field(default=None, max_length=100)
    manager_phone: str | None = Field(default=None, max_length=32)
    manager_wechat: str | None = Field(default=None, max_length=100)
    manager_wechat_qr: str | None = Field(default=None, max_length=255)
    manager_email: str | None = Field(default=None, max_length=255)

    # BM 联系信息
    bm_id: int | None = Field(default=None, description="商务经理用户ID")
    bm_wechat: str | None = Field(default=None, max_length=100, description="BM微信号")
    bm_wechat_qr: str | None = Field(default=None, max_length=500, description="BM微信二维码URL")

    # 图片
    image_urls: list[str] | None = Field(default=None)

    @model_validator(mode="after")
    def compose_address_field(self):
        """如果未显式提供 address，由结构化字段自动拼接"""
        if not self.address:
            self.address = _compose_address(self.country, self.city, self.district, self.street)
        return self


class InstituteUpdate(BaseModel):
    """更新公寓 — 全部可选"""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_cn: str | None = Field(default=None, max_length=200)
    abbreviation: str | None = Field(default=None, max_length=50)

    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    street: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=300)

    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)

    contact_phone: str | None = Field(default=None, max_length=32)
    contact_email: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)

    building_type: str | None = Field(default=None, max_length=50)
    total_floors: int | None = Field(default=None, ge=0)
    year_built: int | None = Field(default=None, ge=1800)
    total_units: int | None = Field(default=None, ge=0)
    has_elevator: bool | None = None
    npc: str | None = Field(default=None, max_length=100)

    description: str | None = Field(default=None, max_length=5000)

    amenities: list[str] | None = None
    female_only: bool | None = None
    couples_allowed: bool | None = None

    manager_name: str | None = Field(default=None, max_length=100)
    manager_phone: str | None = Field(default=None, max_length=32)
    manager_wechat: str | None = Field(default=None, max_length=100)
    manager_wechat_qr: str | None = Field(default=None, max_length=255)
    manager_email: str | None = Field(default=None, max_length=255)

    bm_id: int | None = None
    bm_wechat: str | None = Field(default=None, max_length=100)
    bm_wechat_qr: str | None = Field(default=None, max_length=500)

    image_urls: list[str] | None = None

    @model_validator(mode="after")
    def compose_address_field(self):
        """如果修改了结构化字段但未提供 address，自动拼接"""
        if self.address is None and any([self.country, self.city, self.district, self.street]):
            self.address = _compose_address(self.country, self.city, self.district, self.street)
        return self


class InstituteResponse(BaseModel):
    """公寓响应 — 包含完整结构化地址和新字段"""
    id: int
    name: str
    name_cn: str | None = None
    abbreviation: str | None = None
    address: str | None = None
    # 结构化地址
    country: str | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    postal_code: str | None = None
    npc: str | None = None
    # 坐标
    latitude: float | None = None
    longitude: float | None = None
    # 联系
    contact_phone: str | None = None
    contact_email: str | None = None
    website_url: str | None = None
    description: str | None = None
    # 建筑属性
    building_type: str | None = None
    total_floors: int | None = None
    year_built: int | None = None
    total_units: int | None = None
    has_elevator: bool = False
    # 状态
    status: str
    business_id: str | None = None
    created_by: int
    created_at: datetime | None = None
    # 功能
    amenities: list[str] | None = None
    female_only: bool = False
    couples_allowed: bool = False
    # BM
    bm_id: int | None = None
    bm_wechat: str | None = None
    bm_wechat_qr: str | None = None
    # 图片
    images: list[dict] | None = None

    model_config = {"from_attributes": True}
