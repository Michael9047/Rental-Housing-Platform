"""PMS 对接管理 API — 创建连接、触发同步、预览映射"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin
from app.models.pms_connection import PMSConnection, PMSSyncStatus, PMSType
from app.models.user import User
from app.services.pms.sync_service import PMSSyncService

router = APIRouter()


# ── 请求/响应 Schema ────────────────────────────────────

class PMSConnectionCreate(BaseModel):
    pms_type: PMSType = Field(..., description="PMS 类型: starrez / mews / cloudbeds / ota_xml")
    label: str = Field(..., min_length=1, max_length=100, description="可读标签，如 'Unite Manchester'")
    base_url: str = Field(..., min_length=1, max_length=500, description="PMS API 地址，mock://starrez 表示 Mock")
    api_key: str | None = Field(default=None, max_length=500)
    institute_id: int = Field(..., description="关联的公寓机构 ID")
    room_type_mapping: dict[str, str] | None = Field(default=None, description="房型名称→平台 PropertyType")
    field_map_overrides: dict | None = Field(default=None, description="个性化字段映射覆盖")


class PMSConnectionRead(BaseModel):
    id: int
    pms_type: str
    label: str
    base_url: str
    institute_id: int
    is_active: bool
    sync_status: str
    last_synced_at: str | None = None
    total_properties_synced: int
    last_sync_error: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MappingUpdateRequest(BaseModel):
    room_type_mapping: dict[str, str] | None = Field(default=None)
    field_map_overrides: dict | None = Field(default=None)


# ── 端点 ────────────────────────────────────────────────

@router.post("/connections", status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: PMSConnectionCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    """创建 PMS 对接配置（仅管理员）"""
    conn = PMSConnection(
        pms_type=body.pms_type,
        label=body.label,
        base_url=body.base_url,
        api_key=body.api_key,
        institute_id=body.institute_id,
        room_type_mapping=body.room_type_mapping,
        field_map_overrides=body.field_map_overrides,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return {"id": conn.id, "label": conn.label, "pms_type": conn.pms_type.value}


@router.get("/connections")
async def list_connections(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    institute_id: int | None = Query(default=None),
) -> list[PMSConnectionRead]:
    """列出所有 PMS 对接配置"""
    from sqlalchemy import select
    stmt = select(PMSConnection).order_by(PMSConnection.created_at.desc())
    if institute_id is not None:
        stmt = stmt.where(PMSConnection.institute_id == institute_id)
    result = await session.scalars(stmt)
    return [
        PMSConnectionRead(
            id=c.id, pms_type=c.pms_type.value, label=c.label, base_url=c.base_url,
            institute_id=c.institute_id, is_active=c.is_active, sync_status=c.sync_status.value,
            last_synced_at=c.last_synced_at.isoformat() if c.last_synced_at else None,
            total_properties_synced=c.total_properties_synced,
            last_sync_error=c.last_sync_error,
            created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat(),
        )
        for c in result
    ]


@router.get("/connections/{connection_id}")
async def get_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> PMSConnectionRead:
    """查看单个 PMS 对接详情"""
    conn = await session.get(PMSConnection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="PMS connection not found")
    return PMSConnectionRead(
        id=conn.id, pms_type=conn.pms_type.value, label=conn.label, base_url=conn.base_url,
        institute_id=conn.institute_id, is_active=conn.is_active, sync_status=conn.sync_status.value,
        last_synced_at=conn.last_synced_at.isoformat() if conn.last_synced_at else None,
        total_properties_synced=conn.total_properties_synced,
        last_sync_error=conn.last_sync_error,
        created_at=conn.created_at.isoformat(), updated_at=conn.updated_at.isoformat(),
    )


@router.post("/connections/{connection_id}/sync")
async def trigger_sync(
    connection_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    """手动触发全量同步"""
    sync_service = PMSSyncService(session)
    try:
        stats = await sync_service.sync_connection(connection_id)
        return {"status": "success", **stats}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}") from exc


@router.get("/connections/{connection_id}/preview")
async def preview_mapping(
    connection_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    limit: int = Query(default=5, ge=1, le=50),
) -> list[dict]:
    """预览映射结果（入驻确认用）——不写入数据库"""
    sync_service = PMSSyncService(session)
    try:
        return await sync_service.preview_mapping(connection_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/connections/{connection_id}/mapping")
async def update_mapping(
    connection_id: int,
    body: MappingUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    """更新映射规则（入驻人工精修后）"""
    conn = await session.get(PMSConnection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="PMS connection not found")

    if body.room_type_mapping is not None:
        conn.room_type_mapping = body.room_type_mapping
    if body.field_map_overrides is not None:
        conn.field_map_overrides = body.field_map_overrides

    conn.sync_status = PMSSyncStatus.idle
    await session.commit()
    return {"status": "updated", "id": conn.id}


@router.post("/connections/{connection_id}/deactivate")
async def deactivate_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    """停用 PMS 对接"""
    conn = await session.get(PMSConnection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="PMS connection not found")
    conn.is_active = False
    await session.commit()
    return {"status": "deactivated", "id": conn.id}
