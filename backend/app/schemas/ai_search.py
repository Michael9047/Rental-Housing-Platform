"""AI 搜房 —— 请求/响应 Schema"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 解析阶段
# ---------------------------------------------------------------------------

class MissingField(BaseModel):
    """完整性校验中缺失的字段"""
    field: str = Field(description="字段名，如 district、price_max")
    label: str = Field(description="中文标签")
    hint: str = Field(description="友好的补充提示")


class CompletenessReport(BaseModel):
    """完整性校验报告"""
    is_complete: bool = Field(description="是否所有必填字段都已提供")
    missing_fields: list[MissingField] = Field(default_factory=list)
    summary: str = Field(default="", description="对用户需求的一句话总结")


class ParsedSearchParams(BaseModel):
    """从自然语言中提取的搜索参数"""
    district: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    bedrooms: int | None = None
    property_type: str | None = None
    keywords: str | None = Field(default=None, description="其他关键词，逗号分隔")


class ParseRequest(BaseModel):
    """解析请求"""
    query: str = Field(..., min_length=1, max_length=2000, description="用户自然语言描述")


class ParseResponse(BaseModel):
    """解析响应"""
    params: ParsedSearchParams
    completeness: CompletenessReport


# ---------------------------------------------------------------------------
# 搜索阶段
# ---------------------------------------------------------------------------

class AiSearchRequest(BaseModel):
    """AI 搜索请求"""
    query: str = Field(..., min_length=1, description="用户原始自然语言描述（用于摘要生成）")
    district: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    bedrooms: int | None = None
    property_type: str | None = None
    keywords: str | None = None
    limit: int = Field(default=30, ge=1, le=50)


class AiSearchResponse(BaseModel):
    """AI 搜索响应"""
    summary: str = Field(description="AI 生成的房源摘要文本")
    top_ids: list[int] = Field(default_factory=list, description="摘要中前三的房源 ID")
    results: list["PropertySearchResult"] = Field(default_factory=list)
    total_count: int = Field(default=0)
    search_params: AiSearchRequest


from app.schemas.property import PropertySearchResult  # noqa: E402
AiSearchResponse.model_rebuild()