"""
楼栋管理 API
GET    /buildings          — 列表（按创建者筛选）
POST   /buildings          — 创建楼栋
GET    /buildings/{id}     — 详情
PATCH  /buildings/{id}     — 更新
DELETE /buildings/{id}     — 删除
"""
import re
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session, require_landlord
from app.models.institute import Institute, InstituteStatus
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/buildings", tags=["buildings"])

# 中国大陆手机号：1xx-xxxxxxxxx；固定电话：0xx-xxxxxxxx / xxx-xxxxxxxx
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$")


def _validate_phone(phone: str | None) -> str | None:
    """校验电话号码格式，合法返回 stripped 值，非法抛 422。空值返回 None。"""
    if not phone:
        return None
    stripped = phone.strip()
    if not stripped:
        return None
    if _PHONE_RE.match(stripped):
        return stripped
    raise HTTPException(
        status_code=422,
        detail="联系电话格式不正确，请输入11位手机号或带区号的固定电话",
    )


@router.get("/public")
async def list_public_buildings(
    session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """公开端点——首页展示公寓列表，无需登录"""
    stmt = (select(Institute)
            .options(selectinload(Institute.images))
            .options(selectinload(Institute.unit_types))
            .where(Institute.status == InstituteStatus.active)
            .order_by(Institute.id.desc())
            .offset(skip).limit(limit))
    result = await session.scalars(stmt)
    buildings = []
    for b in result:
        buildings.append({
            "id": b.id, "name": b.name, "name_cn": b.name_cn, "address": b.address,
            "logo_url": b.logo_url, "description": b.description,
            "latitude": float(b.latitude) if b.latitude else None,
            "longitude": float(b.longitude) if b.longitude else None,
            "amenities": b.amenities,
            "female_only": bool(b.female_only) if b.female_only is not None else False,
            "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
            "unit_type_count": len(b.unit_types) if b.unit_types else 0,
            "primary_image": next(({
                "id": img.id, "filename": img.filename,
                "is_primary": img.is_primary,
            } for img in sorted(b.images or [], key=lambda x: x.sort_order)), None),
        })
    return buildings


@router.get("")
async def list_buildings(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    stmt = (select(Institute)
            .options(selectinload(Institute.images))
            .where(Institute.status != InstituteStatus.suspended)  # 排除已删除
            .order_by(Institute.id.desc())
            .offset(skip).limit(limit))
    if current_user.role.value != "admin":
        stmt = stmt.where(Institute.created_by == current_user.id)
    result = await session.scalars(stmt)
    return [{
        "id": b.id, "name": b.name, "address": b.address,
        "contact_phone": b.contact_phone, "contact_email": b.contact_email,
        "logo_url": b.logo_url, "description": b.description,
        "has_api": b.has_api, "status": b.status.value,
        "created_by": b.created_by, "created_at": b.created_at.isoformat() if b.created_at else None,
        "latitude": float(b.latitude) if b.latitude else None,
        "longitude": float(b.longitude) if b.longitude else None,
        "business_id": b.business_id,
        "amenities": b.amenities,
        "female_only": bool(b.female_only) if b.female_only is not None else False,
        "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
        "images": [{"id": img.id, "filename": img.filename, "original_name": img.original_name, "sort_order": img.sort_order, "is_primary": img.is_primary} for img in sorted(b.images or [], key=lambda x: x.sort_order)],
    } for b in result]


@router.post("")
async def create_building(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    # ── 1. 字段提取与校验 ──
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="公寓名称不能为空")
    if len(name) > 200:
        raise HTTPException(status_code=422, detail="公寓名称不能超过200个字符")

    address = (body.get("address") or "").strip() or None
    contact_phone = (body.get("contact_phone") or "").strip() or None
    contact_email = (body.get("contact_email") or "").strip() or None
    description = (body.get("description") or "").strip() or None
    amenities = body.get("amenities") or None

    # ── 2. 同名检查（同一房东下不允许重名） ──
    existing = await session.scalar(
        select(func.count(Institute.id)).where(
            Institute.name == name,
            Institute.created_by == current_user.id,
            Institute.status != InstituteStatus.suspended,
        )
    )
    if existing and existing > 0:
        raise HTTPException(
            status_code=409,
            detail=f"公寓名称「{name}」已存在，请更换名称",
        )

    # ── 3. 创建入库 ──
    from decimal import Decimal
    lat = body.get("latitude")
    lng = body.get("longitude")
    building = Institute(
        name=name,
        address=address,
        contact_phone=contact_phone,
        contact_email=contact_email,
        description=description,
        amenities=amenities,
        female_only=bool(body.get("female_only", False)),
        couples_allowed=bool(body.get("couples_allowed", False)),
        latitude=Decimal(str(lat)) if lat is not None and str(lat).strip() else None,
        longitude=Decimal(str(lng)) if lng is not None and str(lng).strip() else None,
        status=InstituteStatus.active,
        created_by=current_user.id,
    )
    session.add(building)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"公寓名称「{name}」已存在（数据库约束），请更换名称",
        )
    except Exception:
        await session.rollback()
        logger.exception("Failed to create building")
        raise HTTPException(status_code=500, detail="创建公寓失败，服务器内部错误，请稍后重试")

    # ── 图片写入 ──
    image_urls = body.get("image_urls") or []
    logger.info(f"[CREATE] image_urls={image_urls}, lat={building.latitude}, lng={building.longitude}")
    if image_urls:
        from app.models.building_image import BuildingImage
        for i, url in enumerate(image_urls):
            fn = url.rsplit("/", 1)[-1] if "/" in url else url
            img = BuildingImage(institute_id=building.id, filename=fn, original_name=fn, mime_type="image/jpeg", file_size=0, sort_order=i, is_primary=(i == 0))
            session.add(img)
        await session.commit()
        logger.info(f"[CREATE] saved {len(image_urls)} images for building {building.id}")

    # 审计日志
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="创建公寓", resource_type="building", resource_id=building.id, user_id=current_user.id, details={"公寓名": building.name, "地址": building.address})
        session.add(log); await session.commit()
    except Exception: pass
    await session.refresh(building)
    # ── 负责人写入 building_staff ──
    manager_name = (body.get("manager_name") or "").strip()
    manager_phone = (body.get("manager_phone") or "").strip()
    manager_email = (body.get("manager_email") or "").strip()
    if manager_name:
        from app.models.building_staff import BuildingStaff
        staff = BuildingStaff(
            institute_id=building.id,
            name=manager_name,
            role="manager",
            phone=manager_phone or None,
            notes=manager_email or None,
        )
        session.add(staff)
        await session.commit()
    return {
        "id": building.id,
        "name": building.name,
        "address": building.address,
        "contact_phone": building.contact_phone,
        "contact_email": building.contact_email,
        "description": building.description,
        "status": building.status.value,
        "created_by": building.created_by,
        "created_at": building.created_at.isoformat() if building.created_at else None,
        "amenities": building.amenities,
        "female_only": bool(building.female_only),
        "couples_allowed": bool(building.couples_allowed),
    }


@router.get("/recycle-bin")
async def list_deleted_buildings(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=2000),
) -> list[dict]:
    """已删除公寓回收站 — 列出 status=suspended 的公寓"""
    stmt = (select(Institute)
            .options(selectinload(Institute.images))
            .where(Institute.status == InstituteStatus.suspended)
            .order_by(Institute.updated_at.desc())
            .offset(skip).limit(limit))
    if current_user.role.value != "admin":
        stmt = stmt.where(Institute.created_by == current_user.id)
    result = await session.scalars(stmt)
    return [{
        "id": b.id, "name": b.name, "address": b.address,
        "contact_phone": b.contact_phone, "description": b.description,
        "status": b.status.value, "created_by": b.created_by,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        "latitude": float(b.latitude) if b.latitude else None,
        "longitude": float(b.longitude) if b.longitude else None,
        "amenities": b.amenities,
        "images": [{"id": img.id, "filename": img.filename, "original_name": img.original_name, "sort_order": img.sort_order, "is_primary": img.is_primary} for img in sorted(b.images or [], key=lambda x: x.sort_order)],
    } for b in result]


@router.get("/{building_id}")
async def get_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    return {
        "id": b.id, "name": b.name, "address": b.address,
        "contact_phone": b.contact_phone, "contact_email": b.contact_email,
        "logo_url": b.logo_url, "description": b.description,
        "has_api": b.has_api, "status": b.status.value,
        "created_by": b.created_by,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "latitude": float(b.latitude) if b.latitude else None,
        "longitude": float(b.longitude) if b.longitude else None,
        "business_id": b.business_id,
        "amenities": b.amenities,
        "female_only": bool(b.female_only) if b.female_only is not None else False,
        "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
    }


@router.patch("/{building_id}")
async def update_building(
    building_id: int, body: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权修改此楼栋，您只能修改自己创建的公寓")

    new_name = (body.get("name") or "").strip()
    if new_name and new_name != b.name:
        if len(new_name) > 200:
            raise HTTPException(status_code=422, detail="公寓名称不能超过200个字符")
        existing = await session.scalar(
            select(func.count(Institute.id)).where(
                Institute.name == new_name,
                Institute.created_by == current_user.id,
                Institute.id != building_id,
                Institute.status != InstituteStatus.suspended,
            )
        )
        if existing and existing > 0:
            raise HTTPException(status_code=409, detail=f"公寓名称「{new_name}」已存在，请更换名称")

    # 基础字段更新
    for field in ["name", "address", "contact_phone", "contact_email", "description"]:
        val = body.get(field)
        if val is not None and str(val).strip():
            setattr(b, field, str(val).strip())

    # amenities 数组
    if "amenities" in body:
        b.amenities = body["amenities"] if body["amenities"] else None

    # 特殊标记字段
    if "female_only" in body:
        b.female_only = bool(body["female_only"])
    if "couples_allowed" in body:
        b.couples_allowed = bool(body["couples_allowed"])

    # 经纬度
    lat = body.get("latitude")
    lng = body.get("longitude")
    if lat is not None and str(lat).strip():
        from decimal import Decimal
        b.latitude = Decimal(str(lat))
    if lng is not None and str(lng).strip():
        from decimal import Decimal
        b.longitude = Decimal(str(lng))

    # 公寓图集更新
    if "image_urls" in body:
        from app.models.building_image import BuildingImage
        old_imgs = await session.scalars(select(BuildingImage).where(BuildingImage.institute_id == building_id))
        for img in old_imgs: await session.delete(img)
        await session.flush()
        urls = body["image_urls"] or []
        for i, url in enumerate(urls):
            fn = url.rsplit("/", 1)[-1] if "/" in url else url
            img = BuildingImage(institute_id=building_id, filename=fn, original_name=fn, mime_type="image/jpeg", file_size=0, sort_order=i, is_primary=(i == 0))
            session.add(img)
        await session.flush()

    await session.commit()
    await session.refresh(b)

    # ── 负责人同步至 building_staff ──
    manager_name = (body.get("manager_name") or "").strip()
    manager_phone = (body.get("manager_phone") or "").strip()
    manager_email = (body.get("manager_email") or "").strip()
    if manager_name:
        from app.models.building_staff import BuildingStaff
        existing_staff = await session.scalar(
            select(BuildingStaff).where(
                BuildingStaff.institute_id == building_id,
                BuildingStaff.role == "manager",
            )
        )
        if existing_staff:
            existing_staff.name = manager_name
            existing_staff.phone = manager_phone or None
            existing_staff.notes = manager_email or None
        else:
            staff = BuildingStaff(
                institute_id=building_id,
                name=manager_name,
                role="manager",
                phone=manager_phone or None,
                notes=manager_email or None,
            )
            session.add(staff)
        await session.commit()

    # 审计
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="编辑公寓", resource_type="building", resource_id=building_id, details={"公寓名": b.name})
        session.add(log); await session.commit()
    except Exception: pass

    return {
        "id": b.id, "name": b.name, "address": b.address,
        "contact_phone": b.contact_phone, "contact_email": b.contact_email,
        "description": b.description, "status": b.status.value,
        "latitude": float(b.latitude) if b.latitude else None,
        "longitude": float(b.longitude) if b.longitude else None,
        "amenities": b.amenities,
        "female_only": bool(b.female_only) if b.female_only is not None else False,
        "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
    }


@router.delete("/{building_id}")
async def delete_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """级联软删除：公寓 → 户型 → 房间 全部进回收站"""
    from datetime import datetime
    from app.models.unit_type import UnitType
    from app.models.property import Room

    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权删除此楼栋")

    now = datetime.utcnow()
    # 1. 软删除所有下属房间
    room_result = await session.execute(
        select(Room).join(UnitType, Room.unit_type_id == UnitType.id)
        .where(UnitType.institute_id == building_id, Room.deleted_at.is_(None))
    )
    rooms = room_result.scalars().all()
    for r in rooms:
        r.deleted_at = now
        r.status = "offline"

    # 2. 软删除所有下属户型
    ut_result = await session.execute(
        select(UnitType).where(UnitType.institute_id == building_id, UnitType.deleted_at.is_(None))
    )
    unit_types = ut_result.scalars().all()
    for ut in unit_types:
        ut.deleted_at = now

    # 3. 停用公寓本身
    b.status = InstituteStatus.suspended
    await session.commit()

    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="删除公寓", resource_type="building", resource_id=building_id,
                       details={"公寓名": b.name, "级联删除户型": len(unit_types), "级联删除房间": len(rooms)})
        session.add(log); await session.commit()
    except Exception: pass
    return {"ok": True, "cascaded_unit_types": len(unit_types), "cascaded_rooms": len(rooms)}


@router.post("/{building_id}/restore")
async def restore_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """级联恢复：公寓 → 户型 → 房间 全部恢复"""
    from app.models.unit_type import UnitType
    from app.models.property import Room

    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.status != InstituteStatus.suspended:
        raise HTTPException(status_code=400, detail="该公寓不在回收站中")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权操作")

    b.status = InstituteStatus.active

    # 恢复下属户型
    ut_result = await session.execute(
        select(UnitType).where(UnitType.institute_id == building_id, UnitType.deleted_at.isnot(None))
    )
    unit_types = ut_result.scalars().all()
    for ut in unit_types:
        ut.deleted_at = None

    # 恢复下属房间
    room_result = await session.execute(
        select(Room).join(UnitType, Room.unit_type_id == UnitType.id)
        .where(UnitType.institute_id == building_id, Room.deleted_at.isnot(None))
    )
    rooms = room_result.scalars().all()
    for r in rooms:
        r.deleted_at = None
        r.status = "available"

    await session.commit()
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="恢复公寓", resource_type="building", resource_id=building_id,
                       details={"公寓名": b.name, "恢复户型": len(unit_types), "恢复房间": len(rooms)})
        session.add(log); await session.commit()
    except Exception: pass
    return {"ok": True, "id": b.id, "name": b.name, "restored_unit_types": len(unit_types), "restored_rooms": len(rooms)}


@router.delete("/{building_id}/hard", status_code=204)
async def hard_delete_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """硬删除公寓及所有下属户型、房间（不可恢复）"""
    from app.models.unit_type import UnitType
    from app.models.property import Room

    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.status != InstituteStatus.suspended:
        raise HTTPException(status_code=400, detail="请先将公寓移入回收站再硬删除")

    # 硬删除下属房间
    room_result = await session.execute(
        select(Room).join(UnitType, Room.unit_type_id == UnitType.id)
        .where(UnitType.institute_id == building_id)
    )
    for r in room_result.scalars().all():
        await session.delete(r)

    # 硬删除下属户型
    ut_result = await session.execute(
        select(UnitType).where(UnitType.institute_id == building_id)
    )
    for ut in ut_result.scalars().all():
        await session.delete(ut)

    # 硬删除公寓
    name = b.name
    await session.delete(b)
    await session.commit()
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="硬删除公寓", resource_type="building", resource_id=building_id,
                       details={"公寓名": name, "级联删除": f"户型+房间"})
        session.add(log); await session.commit()
    except Exception: pass


# ═══════ 公开公寓列表（租客端） ═══════
@router.get("/public/list")
async def list_public_buildings(
    session: AsyncSession = Depends(get_db_session),
    city: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """租客端公寓列表 — 每栋公寓为一张卡片"""
    stmt = (
        select(Institute)
        .options(selectinload(Institute.images), selectinload(Institute.unit_types))
        .where(Institute.status == InstituteStatus.active)
        .order_by(Institute.id.desc())
    )
    if city:
        stmt = stmt.where(Institute.address.ilike(f"%{city}%"))
    if keyword:
        stmt = stmt.where(or_(Institute.name.ilike(f"%{keyword}%"), Institute.address.ilike(f"%{keyword}%")))
    result = await session.scalars(stmt.limit(limit))
    buildings = list(result.unique())

    items = []
    for b in buildings:
        primary = None
        for img in (b.images or []):
            if img.is_primary: primary = img.filename; break
        if not primary and b.images: primary = b.images[0].filename
        min_rent = None
        for ut in (b.unit_types or []):
            if ut.status.value == "available" and ut.base_rent:
                rent = float(ut.base_rent)
                if min_rent is None or rent < min_rent: min_rent = rent
        items.append({
            "id": b.id, "name": b.name, "address": b.address,
            "latitude": float(b.latitude) if b.latitude else None,
            "longitude": float(b.longitude) if b.longitude else None,
            "description": b.description, "amenities": b.amenities,
            "min_rent": min_rent, "primary_image": primary,
            "unit_type_count": len([ut for ut in (b.unit_types or []) if ut.status.value == "available"]),
            "female_only": bool(b.female_only) if b.female_only is not None else False,
            "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
        })
    return {"items": items, "total": len(items)}


# ═══════ 公寓公开详情（租客端） ═══════
@router.get("/public/{building_id}")
async def get_public_building(
    building_id: int, session: AsyncSession = Depends(get_db_session),
):
    """租客端公寓详情 — 含图集、配套、户型列表"""
    from app.models.unit_type import UnitType
    from app.models.property import Room, RoomStatus
    b = await session.get(Institute, building_id, options=[
        selectinload(Institute.images),
        selectinload(Institute.unit_types).selectinload(UnitType.rooms),
    ])
    if not b or b.status != InstituteStatus.active:
        raise HTTPException(404, "公寓不存在")
    images = [{"id": img.id, "filename": img.filename, "original_name": img.original_name, "sort_order": img.sort_order, "is_primary": img.is_primary} for img in sorted(b.images or [], key=lambda x: x.sort_order)]
    unit_types = []
    for ut in (b.unit_types or []):
        rooms = []
        for r in (ut.rooms or []):
            if r.deleted_at is None and r.status != RoomStatus.offline:
                rooms.append({"id": r.id, "room_number": r.room_number, "floor": r.floor, "special_discount": r.special_discount, "available_from": r.available_from, "status": r.status.value if hasattr(r.status, 'value') else r.status})
        unit_types.append({"id": ut.id, "name": ut.name, "bedrooms": ut.bedrooms, "bathrooms": ut.bathrooms, "hall_count": ut.hall_count, "area_sqm": ut.area_sqm, "base_rent": ut.base_rent, "deposit_amount": ut.deposit_amount, "deposit_type": ut.deposit_type.value if ut.deposit_type and hasattr(ut.deposit_type, 'value') else ut.deposit_type, "amenities": ut.amenities, "image_urls": ut.image_urls, "description": ut.description, "min_stay_months": ut.min_stay_months, "status": ut.status.value if hasattr(ut.status, 'value') else ut.status, "room_count": len(rooms), "rooms": rooms})
    return {"id": b.id, "name": b.name, "address": b.address, "latitude": float(b.latitude) if b.latitude else None, "longitude": float(b.longitude) if b.longitude else None, "description": b.description, "amenities": b.amenities, "contact_phone": b.contact_phone, "images": images, "unit_types": unit_types, "female_only": bool(b.female_only) if b.female_only is not None else False, "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False}
