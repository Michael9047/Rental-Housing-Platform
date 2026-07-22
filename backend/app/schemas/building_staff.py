"""公寓人员 Pydantic 模式"""
from datetime import datetime
from pydantic import BaseModel, Field


class BuildingStaffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="staff", description="manager/sales/staff")
    phone: str | None = None
    notes: str | None = None


class BuildingStaffUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = None
    phone: str | None = None
    notes: str | None = None


class BuildingStaffRead(BaseModel):
    id: int
    institute_id: int
    name: str
    role: str
    phone: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
