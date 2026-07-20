"""维修申请 + 维修师傅模型"""
import enum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text as SAText,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.db.session import Base


class RepairIssueType(str, enum.Enum):
    plumbing = "plumbing"            # 水电
    appliance = "appliance"          # 家电
    carpentry = "carpentry"          # 门窗
    wall_floor = "wall_floor"        # 墙面地面
    plumbing_fixture = "plumbing_fixture"  # 管道
    other = "other"


class RepairStatus(str, enum.Enum):
    pending = "pending"              # 待处理
    assigned = "assigned"            # 已派单
    in_progress = "in_progress"      # 维修中
    completed = "completed"          # 已完成
    rejected = "rejected"            # 已拒绝
    cancelled = "cancelled"          # 已取消


class WorkerStatus(str, enum.Enum):
    available = "available"          # 可调度
    working = "working"              # 工作中
    on_leave = "on_leave"            # 休假


class RepairRequest(TimestampMixin, Base):
    """报修工单"""
    __tablename__ = "repair_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    landlord_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    assigned_worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    issue_type: Mapped[RepairIssueType] = mapped_column(
        Enum(RepairIssueType, name="repair_issue_type"), nullable=False
    )
    description: Mapped[str] = mapped_column(SAText, nullable=False)
    images: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[RepairStatus] = mapped_column(
        Enum(RepairStatus, name="repair_status"),
        default=RepairStatus.pending,
        nullable=False,
        index=True,
    )

    scheduled_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    work_record: Mapped[str | None] = mapped_column(SAText, nullable=True)
    work_images: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 关系
    property: Mapped["Room"] = relationship()
    tenant: Mapped["User"] = relationship(foreign_keys=[tenant_id])
    landlord: Mapped["User"] = relationship(foreign_keys=[landlord_id])
    assigned_worker: Mapped["User | None"] = relationship(foreign_keys=[assigned_worker_id])


class RepairWorker(TimestampMixin, Base):
    """维修师傅档案"""
    __tablename__ = "repair_workers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    manager_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus, name="worker_status"),
        default=WorkerStatus.available,
        nullable=False,
    )
    skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    total_jobs: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=5.0)

    # 关系
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    manager: Mapped["User"] = relationship(foreign_keys=[manager_id])
