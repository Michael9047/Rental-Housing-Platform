"""评价系统 Schema"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.review import ReviewStatus


class ReviewCreate(BaseModel):
    """创建评价请求。

    公寓机构房源：只需填 property_rating, property_comment（landlord 字段留空）
    个人房东房源：property 和 landlord 字段都需填写
    """
    booking_id: int
    property_rating: int = Field(ge=1, le=5, description="房源评分 1-5")
    property_comment: str | None = Field(default=None, max_length=2000)
    property_images: list[str] | None = None

    landlord_rating: int | None = Field(default=None, ge=1, le=5, description="房东评分 1-5（个人房东必填）")
    landlord_comment: str | None = Field(default=None, max_length=2000)
    landlord_images: list[str] | None = None


class ReviewUpdate(BaseModel):
    status: ReviewStatus


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    property_id: int
    landlord_id: int
    booking_id: int | None

    property_rating: int
    property_comment: str | None
    property_images: list | None

    landlord_rating: int | None
    landlord_comment: str | None
    landlord_images: list | None

    status: ReviewStatus
    created_at: datetime
    updated_at: datetime

    # 聚合字段（非 DB 字段，由 service 填充）
    tenant_name: str | None = None
    property_title: str | None = None


class ReviewPublic(BaseModel):
    """公开评价列表（脱敏）"""
    id: int
    property_id: int
    landlord_id: int

    property_rating: int
    property_comment: str | None
    property_images: list | None

    landlord_rating: int | None
    landlord_comment: str | None
    landlord_images: list | None

    created_at: datetime
    tenant_name: str | None = None
    property_title: str | None = None


class ReviewAggregation(BaseModel):
    """评价聚合统计"""
    property_id: int | None = None
    landlord_id: int | None = None
    avg_property_rating: float | None = None
    avg_landlord_rating: float | None = None
    total_reviews: int = 0
