"""房间路由 — 三层架构底层出租单元"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.models.property import Room, RoomStatus
from app.models.unit_type import UnitType
from app.models.institute import Institute
from app.schemas.room import RoomCreate, RoomUpdate, RoomRead, RoomListResponse, RoomImageRead, BatchStatusUpdate, BatchDelete
from app.services.room_service import RoomService

router = APIRouter(tags=["rooms"])


def _get(obj, attr, default=None):
    """安全获取属性，返回 default 或 None"""
    return getattr(obj, attr, None) or default


def _to_read(room) -> RoomRead:
    # 对于 create 路径，数据预加载在 _ut_* / _inst_* 属性上（避免 MissingGreenlet）
    # 安全获取关联数据 — 兜底 _ut_name / _inst_name 等预加载字段
    ut_name = None
    ut = None
    inst = None
    try:
        ut = room.unit_type if room.unit_type else None
        inst = ut.institute if ut and ut.institute else None
        ut_name = ut.name if ut else None
    except Exception:
        ut = None
        inst = None
    # 如果懒加载失败，回退到预加载的私有属性
    if not ut_name:
        ut_name = getattr(room, '_ut_name', None) or '?'

    primary = None
    try:
        imgs = room.images if room.images else []
        for img in imgs:
            if img.is_primary:
                primary = img.filename
                break
    except Exception:
        imgs = []
    try:
        return RoomRead(
        id=room.id,
        landlord_id=room.landlord_id,
        unit_type_id=room.unit_type_id,
        room_number=room.room_number,
        building_block=room.building_block,
        floor=room.floor,
        special_discount=room.special_discount,
        available_from=room.available_from,
        min_stay_months=room.min_stay_months,
        status=room.status.value if hasattr(room.status, "value") else room.status,
        version=room.version,
        deleted_at=room.deleted_at,
        created_at=room.created_at,
        updated_at=room.updated_at,
        unit_type_name=ut_name,
        base_rent=_get(room, '_ut_base_rent') or (_get(ut, 'base_rent') if ut else None),
        area_sqm=_get(room, '_ut_area_sqm') or (_get(ut, 'area_sqm') if ut else None),
        bedrooms=_get(room, '_ut_bedrooms') or (_get(ut, 'bedrooms') if ut else None),
        bathrooms=_get(room, '_ut_bathrooms') or (_get(ut, 'bathrooms') if ut else None),
        hall_count=_get(room, '_ut_hall_count') or (_get(ut, 'hall_count') if ut else None),
        deposit_amount=_get(room, '_ut_deposit_amount') or (_get(ut, 'deposit_amount') if ut else None),
        amenities=_get(room, '_ut_amenities') or (_get(ut, 'amenities') if ut else None),
        institute_id=_get(room, '_inst_id') or (_get(inst, 'id') if inst else None),
        institute_name=_get(room, '_inst_name') or (_get(inst, 'name') if inst else None),
        institute_address=_get(room, '_inst_address') or (_get(inst, 'address') if inst else None),
        images=[RoomImageRead(
            id=img.id, room_id=img.room_id, filename=img.filename,
            original_name=img.original_name, mime_type=img.mime_type,
            file_size=img.file_size, sort_order=img.sort_order,
            is_primary=img.is_primary, created_at=img.created_at,
        ) for img in imgs],
        primary_image_url=primary,
    )
    except Exception:
        return RoomRead(
            id=room.id, landlord_id=room.landlord_id,
            unit_type_id=room.unit_type_id, room_number=room.room_number,
            building_block=room.building_block,
            floor=room.floor, special_discount=room.special_discount,
            available_from=room.available_from, min_stay_months=room.min_stay_months,
            status='available', version=room.version,
            deleted_at=room.deleted_at, created_at=room.created_at,
            updated_at=room.updated_at,
            unit_type_name=None, base_rent=None, area_sqm=None,
            bedrooms=None, bathrooms=None, hall_count=None,
            deposit_amount=None, amenities=None,
            institute_id=None, institute_name=None, institute_address=None,
            images=[], primary_image_url=None,
        )


@router.post("", status_code=201)
async def create_room(
    data: RoomCreate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    room = await RoomService(session).create(data)
    try:
        return _to_read(room)
    except Exception:
        return {"id": room.id, "room_number": room.room_number,
                "unit_type_id": room.unit_type_id, "status": "available",
                "unit_type_name": getattr(room, '_ut_name', '?')}


@router.get("", response_model=RoomListResponse)
async def list_rooms(
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    unit_type_id: int | None = Query(default=None),
    institute_id: int | None = Query(default=None),
    landlord_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
):
    skip = (page - 1) * page_size
    result = await RoomService(session).list(
        skip=skip, limit=page_size, unit_type_id=unit_type_id,
        institute_id=institute_id, landlord_id=landlord_id, status=status,
    )
    items = [_to_read(r) for r in result["items"]]
    return RoomListResponse(
        items=items, total=result["total"], page=result["page"],
        page_size=result["page_size"], total_pages=result["total_pages"],
    )


@router.get("/search")
async def search_rooms(
    q: str | None = Query(default=None, description="关键词搜索"),
    district: str | None = Query(default=None),
    bedrooms: int | None = Query(default=None),
    property_type: str | None = Query(default=None),
    price_min: float | None = Query(default=None),
    price_max: float | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """简单关键词搜索（不依赖 AI/embedding）"""
    filters = [Room.deleted_at.is_(None), Room.status == "available"]
    if q:
        filters.append(
            or_(Room.room_number.ilike(f"%{q}%"), UnitType.name.ilike(f"%{q}%"), Institute.name.ilike(f"%{q}%"))
        )
    if district:
        filters.append(Institute.name.ilike(f"%{district}%"))
    if bedrooms is not None:
        filters.append(UnitType.bedrooms == bedrooms)
    stmt = (
        select(Room)
        .options(selectinload(Room.images), selectinload(Room.unit_type).selectinload(UnitType.institute))
        .join(UnitType, Room.unit_type_id == UnitType.id)
        .join(Institute, UnitType.institute_id == Institute.id)
        .where(and_(*filters))
        .order_by(Room.created_at.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    items = [_to_read(r) for r in result.unique()]
    return {"items": items, "total": len(items)}

@router.get("/audit/recent")
async def get_recent_audit(
    limit: int = Query(default=20),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """修改记录 — 查询当前用户的审计日志"""
    from app.models.audit_log import AuditLog
    stmt = (
        select(AuditLog)
        .where(or_(AuditLog.user_id == current_user.id, AuditLog.user_id.is_(None))).where(~AuditLog.action.ilike("%login%"))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    logs = list(result)
    type_labels = {"room": "房间", "unit_type": "户型", "building": "公寓"}
    return [{
        "id": log.id, "user_id": log.user_id,
        "username": current_user.username,
        "action": log.action, "resource_id": log.resource_id,
        "resource_type": type_labels.get(log.resource_type, log.resource_type),
        "details": log.details,
        "ip_address": log.ip_address,
        "property_title": (log.details or {}).get("房号") or (log.details or {}).get("户型名") or (log.details or {}).get("公寓名") or str(log.resource_id),
        "property_address": None,
        "institute_name": None,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]


# ── 撤销操作 ──
@router.post("/{resource_id}/revert/{audit_id}")
async def revert_audit(
    resource_id: int, audit_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """撤销审计记录 — 支持房间、户型、公寓三层"""
    from app.models.audit_log import AuditLog
    from app.models.unit_type import UnitType
    from app.models.institute import Institute, InstituteStatus

    log = await session.get(AuditLog, audit_id)
    if not log: raise HTTPException(404, "审计记录不存在")

    resource_type = log.resource_type or "room"

    # ── 房间撤销 ──
    if resource_type == "room":
        room = await RoomService(session).get(resource_id)
        if not room: raise HTTPException(404, "房间不存在")
        if log.action == "删除房间":
            room.deleted_at = None; room.status = "available"
            await session.commit()
            return {"message": "已恢复删除的房间", "property_id": resource_id, "reverted_action": "删除房间"}
        elif log.action == "编辑房间" and log.details and "修改内容" in (log.details or {}):
            changes = log.details["修改内容"]
            for field, vals in changes.items():
                old_val = vals.get("旧值") if isinstance(vals, dict) else None
                if old_val is not None and old_val != "" and old_val != "None":
                    try:
                        if hasattr(room, field): setattr(room, field, old_val)
                    except Exception: pass
            room.version += 1; await session.commit()
            return {"message": "已撤销修改", "property_id": resource_id, "reverted_action": "编辑房间"}
        raise HTTPException(400, f"房间操作「{log.action}」暂不支持撤销")

    # ── 户型撤销 ──
    elif resource_type == "unit_type":
        ut = await session.get(UnitType, resource_id)
        if not ut: raise HTTPException(404, "户型不存在")
        if log.action == "删除户型":
            from sqlalchemy import text as sa_text
            await session.execute(sa_text("UPDATE unit_types SET deleted_at = NULL WHERE id = :id"), {"id": resource_id})
            await session.commit()
            return {"message": "已恢复删除的户型", "property_id": resource_id, "reverted_action": "删除户型"}
        elif log.action == "编辑户型" and log.details and "修改内容" in (log.details or {}):
            changes = log.details["修改内容"]
            for field, vals in changes.items():
                old_val = vals.get("旧值") if isinstance(vals, dict) else None
                if old_val is not None and old_val != "" and old_val != "None":
                    try:
                        if hasattr(ut, field):
                            from decimal import Decimal
                            if field in ('base_rent', 'area_sqm', 'deposit_amount'):
                                try: setattr(ut, field, Decimal(str(old_val)))
                                except: pass
                            elif field in ('bedrooms', 'bathrooms', 'hall_count', 'min_stay_months'):
                                try: setattr(ut, field, int(float(old_val)))
                                except: pass
                            else:
                                setattr(ut, field, old_val)
                    except Exception: pass
            await session.commit()
            return {"message": "已撤销修改", "property_id": resource_id, "reverted_action": "编辑户型"}
        raise HTTPException(400, f"户型操作「{log.action}」暂不支持撤销")

    # ── 公寓撤销 ──
    elif resource_type == "building":
        bld = await session.get(Institute, resource_id)
        if not bld: raise HTTPException(404, "公寓不存在")
        if log.action == "删除公寓":
            bld.status = InstituteStatus.active
            await session.commit()
            return {"message": "已恢复删除的公寓", "property_id": resource_id, "reverted_action": "删除公寓"}
        raise HTTPException(400, f"公寓操作「{log.action}」暂不支持撤销")

    raise HTTPException(400, f"未知资源类型「{resource_type}」")


# ── 审计日志管理 ──
@router.delete("/audit/{audit_id}")
async def delete_audit_log(
    audit_id: int, session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    from app.models.audit_log import AuditLog
    log = await session.get(AuditLog, audit_id)
    if not log: raise HTTPException(404, "审计记录不存在")
    await session.delete(log); await session.commit()
    return {"ok": True}


@router.post("/audit/batch-delete")
async def batch_delete_audit(
    body: dict, session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    from app.models.audit_log import AuditLog
    ids = body.get("ids", [])
    if not ids: return {"deleted": 0}
    logs = (await session.scalars(select(AuditLog).where(AuditLog.id.in_(ids)))).all()
    for log in logs: await session.delete(log)
    await session.commit()
    return {"deleted": len(logs)}


@router.post("/audit/clear")
async def clear_audit(
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    from app.models.audit_log import AuditLog
    logs = (await session.scalars(select(AuditLog).where(AuditLog.user_id == _current_user.id))).all()
    for log in logs: await session.delete(log)
    await session.commit()
    return {"deleted": len(logs)}


@router.get("/check-duplicate")
async def check_duplicate(
    unit_type_id: int = Query(...),
    room_number: str = Query(...),
    exclude_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    """检查同户型下房号是否重复"""
    is_dup = await RoomService(session).check_duplicate(unit_type_id, room_number, exclude_id)
    return {"duplicate": is_dup}


@router.get("/recycle-bin", response_model=RoomListResponse)
async def list_deleted_rooms(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=2000),
):
    skip = (page - 1) * page_size
    result = await RoomService(session).list(
        skip=skip, limit=page_size, include_deleted=True,
    )
    items = []
    for r in result["items"]:
        if r.deleted_at is not None:
            try:
                items.append(_to_read(r))
            except Exception:
                pass  # 跳过无法序列化的项
    return RoomListResponse(
        items=items, total=len(items), page=page,
        page_size=page_size, total_pages=max(1, (len(items) + page_size - 1) // page_size),
    )



@router.get("/{room_id}", response_model=RoomRead)
async def get_room(room_id: int, session: AsyncSession = Depends(get_db_session)):
    room = await RoomService(session).get(room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    return _to_read(room)


@router.patch("/{room_id}")
async def update_room(
    room_id: int, data: RoomUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    room = await RoomService(session).update(room_id, data)
    if not room:
        raise HTTPException(404, "房间不存在")
    try:
        return _to_read(room)
    except Exception:
        return {"id": room.id, "room_number": room.room_number,
                "building_block": getattr(room, 'building_block', None),
                "floor": room.floor,
                "status": "available", "version": room.version,
                "unit_type_name": getattr(room, '_ut_name', '?'),
                "institute_name": getattr(room, '_inst_name', '?')}


@router.delete("/{room_id}", status_code=204)
async def delete_room(
    room_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    ok = await RoomService(session).soft_delete(room_id)
    if not ok:
        raise HTTPException(404, "房间不存在或已删除")


@router.post("/{room_id}/restore")
async def restore_room(
    room_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    import logging
    _log = logging.getLogger(__name__)
    try:
        room = await RoomService(session).restore(room_id)
        if not room:
            raise HTTPException(404, "房间不存在或未被删除")
        return _to_read(room)
    except HTTPException:
        raise
    except Exception as e:
        _log.exception(f"Restore room {room_id} failed")
        raise HTTPException(500, f"恢复失败: {e}")


@router.delete("/{room_id}/hard", status_code=204)
async def hard_delete_room(
    room_id: int,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    room = await session.get(Room, room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    room_number = room.room_number
    ok = await RoomService(session).hard_delete(room_id)
    if not ok:
        raise HTTPException(404, "房间不存在")
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="硬删除房间", resource_type="room", resource_id=room_id,
                       details={"房号": room_number})
        session.add(log); await session.commit()
    except Exception: pass


@router.post("/batch/status")
async def batch_update_status(
    data: BatchStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """批量上下架房间"""
    from app.models.property import Room, RoomStatus
    from sqlalchemy import update
    valid_statuses = {s.value for s in RoomStatus}
    if data.status not in valid_statuses:
        raise HTTPException(422, f"无效状态: {data.status}，可选: {valid_statuses}")
    stmt = update(Room).where(Room.id.in_(data.ids), Room.deleted_at.is_(None)).values(status=data.status)
    result = await session.execute(stmt)
    await session.commit()
    return {"success": result.rowcount, "failed": len(data.ids) - result.rowcount}


@router.post("/batch/delete")
async def batch_delete(
    data: BatchDelete,
    session: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(require_landlord),
):
    """批量软删除房间"""
    from datetime import datetime
    from app.models.property import Room, RoomStatus
    from sqlalchemy import update
    stmt = update(Room).where(Room.id.in_(data.ids), Room.deleted_at.is_(None)).values(
        deleted_at=datetime.utcnow(), status="offline"
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"success": result.rowcount, "failed": len(data.ids) - result.rowcount}
