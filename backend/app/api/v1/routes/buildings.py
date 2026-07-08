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
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("")
async def list_buildings(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    stmt = select(Institute).order_by(Institute.id.desc()).offset(skip).limit(limit)
    if current_user.role.value != "admin":
        stmt = stmt.where(Institute.created_by == current_user.id)
    result = await session.scalars(stmt)
    return [{
        "id": b.id, "name": b.name, "address": b.address,
        "contact_phone": b.contact_phone, "contact_email": b.contact_email,
        "logo_url": b.logo_url, "description": b.description,
        "has_api": b.has_api, "status": b.status.value,
        "created_by": b.created_by, "created_at": b.created_at.isoformat() if b.created_at else None,
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
    contact_phone = _validate_phone(body.get("contact_phone"))
    contact_email = (body.get("contact_email") or "").strip() or None
    description = (body.get("description") or "").strip() or None

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
    building = Institute(
        name=name,
        address=address,
        contact_phone=contact_phone,
        contact_email=contact_email,
        description=description,
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

    await session.refresh(building)
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
    }


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
        # 检查新名称是否与房东其他公寓重名
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

    for field in ["name", "address", "contact_phone", "contact_email", "description"]:
        val = body.get(field)
        if val is not None and str(val).strip():
            cleaned = str(val).strip()
            if field == "contact_phone" and cleaned:
                cleaned = _validate_phone(cleaned)  # 抛 422 如果格式不对
            setattr(b, field, cleaned)

    await session.commit()
    await session.refresh(b)
    return {
        "id": b.id, "name": b.name, "address": b.address,
        "contact_phone": b.contact_phone, "contact_email": b.contact_email,
        "description": b.description, "status": b.status.value,
    }


@router.delete("/{building_id}")
async def delete_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权删除此楼栋")
    # 检查是否有关联房源
    from sqlalchemy import func
    from app.models.property import Property
    count = await session.scalar(
        select(func.count(Property.id)).where(Property.institute_id == building_id)
    )
    if count and count > 0:
        raise HTTPException(status_code=400, detail="该楼栋下仍有房源，请先删除或转移房源")
    b.status = InstituteStatus.suspended
    await session.commit()
    return {"ok": True}
