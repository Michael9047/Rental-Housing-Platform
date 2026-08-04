"""合同模板 Pydantic 模式"""
from datetime import datetime
from pydantic import BaseModel, Field


class FieldPosition(BaseModel):
    """单个字段坐标"""
    page: int = Field(default=1, ge=1)
    x: float = Field(..., description="X坐标(pt)")
    y: float = Field(..., description="Y坐标(pt)")
    font_size: int = Field(default=12, ge=6, le=48)
    width: float | None = Field(default=None)


class TemplateCreate(BaseModel):
    """上传模板 — name 必填"""
    name: str = Field(..., min_length=1, max_length=100)


class TemplateUpdate(BaseModel):
    """更新模板名称或保存坐标"""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    field_positions: dict[str, FieldPosition] | None = None
    is_active: bool | None = None


class TemplateRead(BaseModel):
    """模板响应"""
    id: str
    bm_id: int
    name: str
    file_path: str
    field_positions: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: list[TemplateRead]
    total: int
