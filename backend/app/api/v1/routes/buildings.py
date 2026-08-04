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
from app.schemas.institute import InstituteCreate, InstituteUpdate

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


def _build_card(b: Institute) -> dict:
    """构建公寓卡片数据 — 含价格区间、图片等展示字段"""
    uts = b.unit_types or []
    available_uts = [ut for ut in uts if ut.deleted_at is None and ut.status.value == "available"]
    prices = [float(ut.base_rent) for ut in available_uts if ut.base_rent]
    min_rent = min(prices) if prices else None
    max_rent = max(prices) if prices else None
    primary = None
    for img in sorted(b.images or [], key=lambda x: x.sort_order):
        if img.is_primary:
            primary = {"id": img.id, "filename": img.filename, "is_primary": True}
            break
    if not primary and b.images:
        img = sorted(b.images, key=lambda x: x.sort_order)[0]
        primary = {"id": img.id, "filename": img.filename, "is_primary": img.is_primary}
    # 户型类型汇总
    pt_set = set(getattr(ut, 'property_type', None) for ut in available_uts)
    pt_vals = [v for v in pt_set if v]
    property_type = pt_vals[0] if len(pt_vals) == 1 else None
    # 户型标签列表（如 ["studio","1bed","2bed"]）
    pt_labels: dict = {"studio":"Studio","ensuite":"Ensuite","1bed":"一室","2bed":"两室","3bed":"三室","4bed":"四室","5bed+":"五室+","shared":"合租"}
    unit_type_tags = [pt_labels.get(v.value if hasattr(v,'value') else str(v), str(v)) for v in pt_set if v]
    return {
        "id": b.id, "name": b.name, "name_cn": b.name_cn, "address": b.address,
        "country": b.country, "city": b.city, "district": b.district,
        "logo_url": b.logo_url, "description": b.description,
        "latitude": float(b.latitude) if b.latitude else None,
        "longitude": float(b.longitude) if b.longitude else None,
        "amenities": b.amenities,
        "female_only": bool(b.female_only) if b.female_only is not None else False,
        "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False,
        "unit_type_count": len(available_uts),
        "unit_type_tags": unit_type_tags,
        "min_rent": min_rent, "max_rent": max_rent,
        "avg_bedrooms": 0,
        "property_type": property_type.value if hasattr(property_type, 'value') else str(property_type) if property_type else None,
        "primary_image": primary,
        "images": [{"id": img.id, "filename": img.filename, "original_name": img.original_name,
                     "sort_order": img.sort_order, "is_primary": img.is_primary}
                   for img in sorted(b.images or [], key=lambda x: x.sort_order)],
        "institute_id": b.id,
        "institute_name": b.name,
    }


from math import radians, cos, sin, asin, sqrt as _sqrt

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 距离（km）"""
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(_sqrt(a))

async def _search_buildings(
    session: AsyncSession,
    q: str | None = None,
    district: str | None = None,
    country: str | None = None,
    city: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    property_type: str | None = None,
    sort_by: str | None = None,
    near_lat: float | None = None,
    near_lng: float | None = None,
    near_distance_km: float | None = 5.0,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    stmt = (select(Institute)
            .options(selectinload(Institute.images))
            .options(selectinload(Institute.unit_types))
            .where(Institute.status == InstituteStatus.active))
    if q:
        stmt = stmt.where(or_(
            Institute.name.ilike(f"%{q}%"),
            Institute.name_cn.ilike(f"%{q}%"),
            Institute.address.ilike(f"%{q}%"),
        ))
    if district:
        stmt = stmt.where(Institute.district.ilike(f"%{district}%"))
    if country:
        stmt = stmt.where(Institute.country == country)
    if city:
        stmt = stmt.where(Institute.city.ilike(f"%{city}%"))
    if sort_by == 'price_asc':
        stmt = stmt.order_by(Institute.id.asc())
    elif sort_by == 'price_desc':
        stmt = stmt.order_by(Institute.id.desc())
    elif sort_by == 'created_at':
        stmt = stmt.order_by(Institute.created_at.desc())
    else:
        stmt = stmt.order_by(Institute.id.desc())
    stmt = stmt.offset(skip).limit(limit if limit <= 200 else 200)
    result = await session.scalars(stmt)
    cards = [_build_card(b) for b in result]

    # 客户端过滤（价格 / 户型 / 地理位置）
    if price_min is not None:
        cards = [c for c in cards if c.get("min_rent") is not None and c["min_rent"] >= price_min]
    if price_max is not None:
        cards = [c for c in cards if c.get("min_rent") is not None and c["min_rent"] <= price_max]
    if property_type:
        cards = [c for c in cards if c.get("property_type") == property_type]
    if near_lat is not None and near_lng is not None and near_distance_km:
        cards = [c for c in cards if c.get("latitude") and c.get("longitude")
                 and _haversine(near_lat, near_lng, float(c["latitude"]), float(c["longitude"])) <= near_distance_km]

    # 按价格排序（需在过滤后）
    if sort_by == 'price_asc':
        cards.sort(key=lambda c: c.get("min_rent") or 0)
    elif sort_by == 'price_desc':
        cards.sort(key=lambda c: c.get("min_rent") or 0, reverse=True)

    return cards


@router.get("/public")
async def list_public_buildings(
    session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """公开端点——首页展示公寓列表，无需登录"""
    return await _search_buildings(session, skip=skip, limit=limit)


@router.get("/public/search")
async def search_public_buildings(
    session: AsyncSession = Depends(get_db_session),
    q: str | None = Query(default=None),
    district: str | None = Query(default=None),
    country: str | None = Query(default=None),
    city: str | None = Query(default=None),
    price_min: int | None = Query(default=None),
    price_max: int | None = Query(default=None),
    property_type: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    near_lat: float | None = Query(default=None),
    near_lng: float | None = Query(default=None),
    near_distance_km: float | None = Query(default=5.0),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """公开搜索——按名称/区域/价格/户型搜索公寓，返回卡片级数据"""
    return await _search_buildings(
        session, q=q, district=district, country=country, city=city,
        price_min=price_min, price_max=price_max, property_type=property_type,
        sort_by=sort_by, near_lat=near_lat, near_lng=near_lng,
        near_distance_km=near_distance_km, skip=skip, limit=limit,
    )


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
        "country": b.country, "city": b.city, "district": b.district,
        "street": b.street, "postal_code": b.postal_code,
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
    body: InstituteCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    # ── 1. 字段提取与校验（Pydantic 已完成基础校验）──
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="公寓名称不能为空")

    # address 由 model_validator 自动从结构化字段拼接（如未显式提供）
    address = body.address.strip() if body.address else None
    contact_phone = body.contact_phone.strip() if body.contact_phone else None
    contact_email = body.contact_email.strip() if body.contact_email else None
    description = body.description.strip() if body.description else None
    amenities = body.amenities or None

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
    lat = body.latitude
    lng = body.longitude
    building = Institute(
        name=name,
        address=address,
        country=body.country.strip() if body.country else None,
        city=body.city.strip() if body.city else None,
        district=body.district.strip() if body.district else None,
        street=body.street.strip() if body.street else None,
        postal_code=body.postal_code.strip() if body.postal_code else None,
        contact_phone=contact_phone,
        contact_email=contact_email,
        description=description,
        amenities=amenities,
        female_only=body.female_only,
        couples_allowed=body.couples_allowed,
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

    # ── 图片写入 + 从 temp 移动到主目录 ──
    image_urls = body.image_urls or []
    if image_urls:
        import shutil
        from pathlib import Path
        from app.core.config import get_settings
        from app.models.building_image import BuildingImage
        settings = get_settings()
        upload_root = Path(settings.upload_dir).resolve()
        for i, url in enumerate(image_urls):
            fn = url.rsplit("/", 1)[-1] if "/" in url else url
            # 将临时文件从 temp/ 移到 uploads/ 根目录
            src = None
            if "/temp/" in url:
                rel = url.split("/api/v1/uploads/", 1)[-1] if "/api/v1/uploads/" in url else None
                if rel:
                    src = upload_root / rel
            img = BuildingImage(institute_id=building.id, filename=fn, original_name=fn, mime_type="image/jpeg", file_size=0, sort_order=i, is_primary=(i == 0))
            session.add(img)
            # 移动文件
            logger.warning(f"[IMAGE MOVE] checking: src={src} exists={src.exists() if src else False}")
            if src and src.exists():
                dst = upload_root / fn
                try:
                    shutil.move(str(src), str(dst))
                    logger.warning(f"[IMAGE MOVE] OK: {src} -> {dst}")
                except Exception as e:
                    logger.warning(f"[IMAGE MOVE] FAIL: {src} -> {dst}: {e}")
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
    manager_name = body.manager_name.strip() if body.manager_name else ""
    manager_phone = body.manager_phone.strip() if body.manager_phone else ""
    manager_email = body.manager_email.strip() if body.manager_email else ""
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
        "country": building.country, "city": building.city,
        "district": building.district, "street": building.street,
        "postal_code": building.postal_code,
        "contact_phone": building.contact_phone,
        "contact_email": building.contact_email,
        "description": building.description,
        "status": building.status.value,
        "created_by": building.created_by,
        "created_at": building.created_at.isoformat() if building.created_at else None,
        "latitude": float(building.latitude) if building.latitude else None,
        "longitude": float(building.longitude) if building.longitude else None,
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
        "country": b.country, "city": b.city, "district": b.district,
        "street": b.street, "postal_code": b.postal_code,
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
        "country": b.country, "city": b.city, "district": b.district,
        "street": b.street, "postal_code": b.postal_code,
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


def _ev(obj, attr):
    """安全获取枚举值：如果是枚举返回 .value，否则返回字符串"""
    v = getattr(obj, attr, None)
    if v is None: return None
    return v.value if hasattr(v, 'value') else str(v)


@router.get("/{building_id}/tenant-detail")
async def get_tenant_building_detail(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """租客端公寓详情 — 返回楼栋 + 户型 + 图片"""
    b = await session.get(Institute, building_id,
        options=[selectinload(Institute.unit_types), selectinload(Institute.images)])
    if not b or b.status != InstituteStatus.active:
        raise HTTPException(status_code=404, detail="楼栋不存在")

    uts = []
    for ut in (b.unit_types or []):
        if ut.deleted_at is not None: continue
        uts.append({
            "id": ut.id, "name": ut.name,
            "property_type": _ev(ut, 'property_type'),
            "bedrooms": ut.bedrooms, "bathrooms": ut.bathrooms,
            "hall_count": ut.hall_count,
            "area_sqm": float(ut.area_sqm) if ut.area_sqm else None,
            "base_rent": float(ut.base_rent) if ut.base_rent else 0,
            "deposit_amount": ut.deposit_amount,
            "deposit_type": _ev(ut, 'deposit_type'),
            "currency": ut.currency,
            "amenities": ut.amenities,
            "image_urls": ut.image_urls,
            "description": ut.description,
            "available_from": ut.available_from.isoformat() if ut.available_from else None,
            "min_stay_months": ut.min_stay_months,
            "has_vacancy": ut.has_vacancy,
            "total_count": ut.total_count,
            "available_count": ut.available_count,
            "status": _ev(ut, 'status') or "available",
            "created_at": ut.created_at.isoformat() if ut.created_at else None,
        })

    return {
        "id": b.id, "name": b.name, "name_cn": b.name_cn,
        "address": b.address,
        "country": b.country, "city": b.city, "district": b.district,
        "street": b.street, "postal_code": b.postal_code,
        "latitude": float(b.latitude) if b.latitude else None,
        "longitude": float(b.longitude) if b.longitude else None,
        "contact_phone": b.contact_phone, "contact_email": b.contact_email,
        "website_url": b.website_url,
        "logo_url": b.logo_url, "description": b.description,
        "amenities": b.amenities,
        "female_only": bool(b.female_only),
        "couples_allowed": bool(b.couples_allowed),
        "building_type": b.building_type,
        "total_floors": b.total_floors, "year_built": b.year_built,
        "total_units": b.total_units, "has_elevator": bool(b.has_elevator),
        "bm_wechat": b.bm_wechat, "bm_wechat_qr": b.bm_wechat_qr,
        "status": b.status.value if hasattr(b.status, 'value') else str(b.status),
        "business_id": b.business_id,
        "images": [{"id": img.id, "filename": img.filename, "original_name": img.original_name,
                     "sort_order": img.sort_order, "is_primary": img.is_primary}
                   for img in sorted(b.images or [], key=lambda x: x.sort_order)],
        "unit_types": uts,
    }


@router.patch("/{building_id}")
async def update_building(
    building_id: int, body: InstituteUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权修改此楼栋，您只能修改自己创建的公寓")

    # 获取客户端实际发送的字段（排除未设置的）
    data = body.model_dump(exclude_unset=True)

    new_name = (body.name or "").strip() if body.name else ""
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

    # 基础字段更新（包含结构化地址字段）
    text_fields = ["name", "address", "country", "city", "district", "street",
                   "postal_code", "contact_phone", "contact_email", "description"]
    for field in text_fields:
        if field in data and data[field] is not None:
            val = str(data[field]).strip()
            if val:
                setattr(b, field, val)

    # amenities 数组
    if "amenities" in data:
        b.amenities = data["amenities"] if data["amenities"] else None

    # 特殊标记字段
    if "female_only" in data:
        b.female_only = bool(data["female_only"])
    if "couples_allowed" in data:
        b.couples_allowed = bool(data["couples_allowed"])

    # 经纬度
    if "latitude" in data and data["latitude"] is not None:
        from decimal import Decimal
        b.latitude = Decimal(str(data["latitude"]))
    if "longitude" in data and data["longitude"] is not None:
        from decimal import Decimal
        b.longitude = Decimal(str(data["longitude"]))

    # 公寓图集更新
    if "image_urls" in data:
        import shutil
        from pathlib import Path
        from app.core.config import get_settings
        from app.models.building_image import BuildingImage
        settings = get_settings()
        upload_root = Path(settings.upload_dir).resolve()
        old_imgs = await session.scalars(select(BuildingImage).where(BuildingImage.institute_id == building_id))
        for img in old_imgs: await session.delete(img)
        await session.flush()
        urls = data["image_urls"] or []
        for i, url in enumerate(urls):
            fn = url.rsplit("/", 1)[-1] if "/" in url else url
            src = None
            if "/temp/" in url:
                rel = url.split("/api/v1/uploads/", 1)[-1] if "/api/v1/uploads/" in url else None
                if rel: src = upload_root / rel
            img = BuildingImage(institute_id=building_id, filename=fn, original_name=fn, mime_type="image/jpeg", file_size=0, sort_order=i, is_primary=(i == 0))
            session.add(img)
            if src and src.exists():
                dst = upload_root / fn
                try: shutil.move(str(src), str(dst))
                except Exception: pass
        await session.flush()

    await session.commit()
    await session.refresh(b)

    # ── 负责人同步至 building_staff ──
    manager_name = body.manager_name.strip() if body.manager_name else ""
    manager_phone = body.manager_phone.strip() if body.manager_phone else ""
    manager_email = body.manager_email.strip() if body.manager_email else ""
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
        "country": b.country, "city": b.city, "district": b.district,
        "street": b.street, "postal_code": b.postal_code,
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
    """级联软删除：公寓 → 户型 全部进回收站"""
    from datetime import datetime
    from app.models.unit_type import UnitType

    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权删除此楼栋")

    now = datetime.utcnow()

    # 1. 软删除所有下属户型（Room 表已在三层改两层重构中移除）
    ut_result = await session.execute(
        select(UnitType).where(UnitType.institute_id == building_id, UnitType.deleted_at.is_(None))
    )
    unit_types = ut_result.scalars().all()
    for ut in unit_types:
        ut.deleted_at = now

    # 2. 停用公寓本身
    b.status = InstituteStatus.suspended
    await session.commit()

    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="删除公寓", resource_type="building", resource_id=building_id,
                       details={"公寓名": b.name, "级联删除户型": len(unit_types)})
        session.add(log); await session.commit()
    except Exception: pass
    return {"ok": True, "cascaded_unit_types": len(unit_types)}


@router.post("/{building_id}/restore")
async def restore_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> dict:
    """级联恢复：公寓 → 户型 全部恢复"""
    from app.models.unit_type import UnitType

    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.status != InstituteStatus.suspended:
        raise HTTPException(status_code=400, detail="该公寓不在回收站中")
    if b.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="无权操作")

    b.status = InstituteStatus.active

    # 恢复下属户型（Room 表已在三层改两层重构中移除）
    ut_result = await session.execute(
        select(UnitType).where(UnitType.institute_id == building_id, UnitType.deleted_at.isnot(None))
    )
    unit_types = ut_result.scalars().all()
    for ut in unit_types:
        ut.deleted_at = None

    await session.commit()
    try:
        from app.models.audit_log import AuditLog
        log = AuditLog(action="恢复公寓", resource_type="building", resource_id=building_id,
                       details={"公寓名": b.name, "恢复户型": len(unit_types)})
        session.add(log); await session.commit()
    except Exception: pass
    return {"ok": True, "id": b.id, "name": b.name, "restored_unit_types": len(unit_types)}


@router.delete("/{building_id}/hard", status_code=204)
async def hard_delete_building(
    building_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
):
    """硬删除公寓及所有下属户型（不可恢复）"""
    from app.models.unit_type import UnitType

    b = await session.get(Institute, building_id)
    if not b:
        raise HTTPException(status_code=404, detail="楼栋不存在")
    if b.status != InstituteStatus.suspended:
        raise HTTPException(status_code=400, detail="请先将公寓移入回收站再硬删除")

    # 硬删除下属户型（Room 表已在三层改两层重构中移除）
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
                       details={"公寓名": name, "级联删除": "户型"})
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
            "country": b.country, "city": b.city, "district": b.district,
            "street": b.street, "postal_code": b.postal_code,
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
    b = await session.get(Institute, building_id, options=[
        selectinload(Institute.images),
        selectinload(Institute.unit_types),  # Room 关系已移除（三层改两层重构）
    ])
    if not b or b.status != InstituteStatus.active:
        raise HTTPException(404, "公寓不存在")
    images = [{"id": img.id, "filename": img.filename, "original_name": img.original_name, "sort_order": img.sort_order, "is_primary": img.is_primary} for img in sorted(b.images or [], key=lambda x: x.sort_order)]
    unit_types = []
    for ut in (b.unit_types or []):
        if ut.deleted_at is not None:
            continue
        unit_types.append({"id": ut.id, "name": ut.name, "bedrooms": ut.bedrooms, "bathrooms": ut.bathrooms, "hall_count": ut.hall_count, "area_sqm": ut.area_sqm, "base_rent": ut.base_rent, "deposit_amount": ut.deposit_amount, "deposit_type": ut.deposit_type.value if ut.deposit_type and hasattr(ut.deposit_type, 'value') else ut.deposit_type, "amenities": ut.amenities, "image_urls": ut.image_urls, "description": ut.description, "min_stay_months": ut.min_stay_months, "status": ut.status.value if hasattr(ut.status, 'value') else ut.status})
    return {"id": b.id, "name": b.name, "address": b.address, "country": b.country, "city": b.city, "district": b.district, "street": b.street, "postal_code": b.postal_code, "latitude": float(b.latitude) if b.latitude else None, "longitude": float(b.longitude) if b.longitude else None, "description": b.description, "amenities": b.amenities, "contact_phone": b.contact_phone, "images": images, "unit_types": unit_types, "female_only": bool(b.female_only) if b.female_only is not None else False, "couples_allowed": bool(b.couples_allowed) if b.couples_allowed is not None else False}
