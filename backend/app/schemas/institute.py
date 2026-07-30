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
    description: str | None = Field(default=None, max_length=5000)

    amenities: list[str] | None = None
    female_only: bool | None = None
    couples_allowed: bool | None = None

    manager_name: str | None = Field(default=None, max_length=100)
    manager_phone: str | None = Field(default=None, max_length=32)
    manager_wechat: str | None = Field(default=None, max_length=100)
    manager_wechat_qr: str | None = Field(default=None, max_length=255)
    manager_email: str | None = Field(default=None, max_length=255)

    image_urls: list[str] | None = None

    @model_validator(mode="after")
    def compose_address_field(self):
        """如果修改了结构化字段但未提供 address，自动拼接"""
        if self.address is None and any([self.country, self.city, self.district, self.street]):
            self.address = _compose_address(self.country, self.city, self.district, self.street)
        return self


class InstituteResponse(BaseModel):
    """公寓响应 — 包含完整结构化地址"""
    id: int
    name: str
    address: str | None = None
    # 结构化地址
    country: str | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    postal_code: str | None = None
    # 坐标
    latitude: float | None = None
    longitude: float | None = None
    # 联系
    contact_phone: str | None = None
    contact_email: str | None = None
    description: str | None = None
    # 状态
    status: str
    business_id: str | None = None
    created_by: int
    created_at: datetime | None = None
    # 功能
    amenities: list[str] | None = None
    female_only: bool = False
    couples_allowed: bool = False
    # 图片
    images: list[dict] | None = None

    model_config = {"from_attributes": True}
