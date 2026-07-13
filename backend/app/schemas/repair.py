"""维修系统 Pydantic 验证模型"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.repair import RepairIssueType, RepairStatus, WorkerStatus


# ── 报修工单 ──────────────────────────────────────

class RepairCreate(BaseModel):
    """租客创建报修"""
    property_id: int
    issue_type: RepairIssueType
    description: str = Field(min_length=1, max_length=2000)
    images: list[str] | None = None
    scheduled_time: str | None = None  # 格式: "YYYY-MM-DD AM/PM"


class RepairUpdate(BaseModel):
    """房东/维修师傅更新工单"""
    status: RepairStatus | None = None
    assigned_worker_id: int | None = None
    work_record: str | None = None
    work_images: list[str] | None = None


class RepairRead(BaseModel):
    """工单详情"""
    id: int
    property_id: int
    tenant_id: int
    landlord_id: int
    assigned_worker_id: int | None = None
    issue_type: RepairIssueType
    description: str
    images: list[str] | None = None
    status: RepairStatus
    scheduled_time: str | None = None
    completed_at: str | None = None
    work_record: str | None = None
    work_images: list[str] | None = None
    created_at: str
    updated_at: str

    # 关联对象
    tenant_name: str | None = None
    landlord_name: str | None = None
    worker_name: str | None = None
    property_title: str | None = None

    model_config = {"from_attributes": True}


# ── 维修师傅 ──────────────────────────────────────

class WorkerCreate(BaseModel):
    """房东创建维修师傅"""
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6)
    phone: str = Field(min_length=1, max_length=32)
    skills: list[str] | None = None


class WorkerUpdate(BaseModel):
    """更新维修师傅信息"""
    phone: str | None = None
    skills: list[str] | None = None


class WorkerStatusUpdate(BaseModel):
    """调整维修师傅工作状态"""
    status: WorkerStatus


class WorkerRead(BaseModel):
    """维修师傅详情"""
    id: int
    user_id: int
    manager_id: int
    status: WorkerStatus
    skills: list[str] | None = None
    phone: str
    total_jobs: int
    rating: float
    created_at: str
    username: str | None = None  # 关联 User

    model_config = {"from_attributes": True}
