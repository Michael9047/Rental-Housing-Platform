"""户型服务层"""
import shutil
import uuid as _uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.unit_type import UnitType, UnitTypeImage
from app.models.audit_log import AuditLog
from app.schemas.unit_type import UnitTypeCreate, UnitTypeUpdate


def _move_temp_images(urls: list[str]) -> list[str]:
    """将临时上传的图片从 temp/ 移到 uploads/ 根目录"""
    from app.core.config import get_settings
    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    result = []
    for url in urls:
        fn = url.rsplit("/", 1)[-1] if "/" in url else url
        src = None
        if "/temp/" in url and "/api/v1/uploads/" in url:
            rel = url.split("/api/v1/uploads/", 1)[-1]
            src = upload_root / rel
        if src and src.exists():
            dst = upload_root / fn
            try:
                shutil.move(str(src), str(dst))
            except Exception:
                pass
        result.append(fn)
    return result


class UnitTypeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _audit(self, action: str, resource_id: int, details: dict | None = None):
        try:
            log = AuditLog(action=action, resource_type="unit_type", resource_id=resource_id, details=details)
            self.session.add(log)
            await self.session.commit()
        except Exception:
            pass

    async def create(self, data: UnitTypeCreate) -> UnitType:
        from app.core.business_id import generate_business_id
        biz_id = await generate_business_id(self.session, "unit_type")
        ut = UnitType(
            uuid=str(_uuid.uuid4()),
            business_id=biz_id,
            institute_id=data.institute_id, name=data.name,
            bedrooms=data.bedrooms, bathrooms=data.bathrooms, hall_count=data.hall_count,
            area_sqm=data.area_sqm, base_rent=data.base_rent,
            deposit_amount=data.deposit_amount, deposit_type=data.deposit_type,
            lease_start=data.lease_start, lease_start_date=data.lease_start_date,
            lease_end=data.lease_end, lease_end_date=data.lease_end_date,
            currency=data.currency, special_offer=data.special_offer,
            floor_pricing=data.floor_pricing, amenities=data.amenities,
            description=data.description,
            available_from=data.available_from, min_stay_months=data.min_stay_months,
            status=data.status,
        )
        self.session.add(ut)
        await self.session.commit()
        await self.session.refresh(ut)

        from app.models.institute import Institute
        inst = await self.session.get(Institute, ut.institute_id)
        inst_name = inst.name if inst else ""
        desc = f"在「{inst_name}」公寓下创建了户型「{ut.name}」（{ut.bedrooms}室{ut.hall_count}厅{ut.bathrooms}卫，{ut.area_sqm}㎡，¥{ut.base_rent}/月）"
        await self._audit("创建户型", ut.id, {"描述": desc, "户型名": ut.name, "公寓": inst_name, "月租": str(ut.base_rent)})

        if ut.institute_id:
            inst = await self.session.get(Institute, ut.institute_id)
            ut._institute_name = inst.name if inst else None
            ut._institute_business_id = inst.business_id if inst else None
        return ut

    async def get(self, unit_type_id: int) -> UnitType | None:
        return await self.session.get(UnitType, unit_type_id, options=[
            selectinload(UnitType.institute),
            selectinload(UnitType.images),
        ])

    async def list(self, *, skip: int = 0, limit: int = 20, institute_id: int | None = None) -> dict:
        filters = [UnitType.deleted_at.is_(None)]
        if institute_id is not None:
            filters.append(UnitType.institute_id == institute_id)
        base = select(func.count(UnitType.id))
        for f in filters: base = base.where(f)
        total = (await self.session.scalar(base)) or 0
        stmt = (select(UnitType)
                .options(selectinload(UnitType.institute), selectinload(UnitType.images))
                .order_by(UnitType.created_at.desc()).offset(skip).limit(limit))
        for f in filters: stmt = stmt.where(f)
        result = await self.session.scalars(stmt)
        items = list(result.unique())
        from app.models.property import Room
        for ut in items:
            rc = select(func.count(Room.id)).where(Room.unit_type_id == ut.id)
            ut._room_count = (await self.session.scalar(rc)) or 0
        return {"items": items, "total": total, "page": skip // limit + 1, "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}

    async def update(self, unit_type_id: int, data: UnitTypeUpdate) -> UnitType | None:
        ut = await self.get(unit_type_id)
        if not ut: return None
        update_data = data.model_dump(exclude_unset=True)
        old_vals = {k: str(getattr(ut, k, '') or '') for k in update_data}
        for k, v in update_data.items(): setattr(ut, k, v)
        await self.session.commit()
        await self.session.refresh(ut)
        from app.models.institute import Institute
        inst = await self.session.get(Institute, ut.institute_id)
        ut._institute_name = inst.name if inst else None
        ut._institute_business_id = inst.business_id if inst else None
        changes = {k: {"新值": str(v), "旧值": old_vals.get(k, '')} for k, v in update_data.items()}
        await self._audit("编辑户型", ut.id, {"户型名": ut.name, "修改内容": changes})
        return ut

    async def delete(self, unit_type_id: int) -> bool:
        from datetime import datetime
        from app.models.property import Room
        ut = await self.get(unit_type_id)
        if not ut: return False
        name = ut.name
        now = datetime.utcnow()
        room_result = await self.session.execute(
            select(Room).where(Room.unit_type_id == unit_type_id, Room.deleted_at.is_(None))
        )
        for r in room_result.scalars().all():
            r.deleted_at = now
            r.status = "offline"
        ut.deleted_at = now
        await self.session.commit()
        await self._audit("删除户型", unit_type_id, {"户型名": name, "级联删除房间": 0})
        return True

    async def restore(self, unit_type_id: int) -> UnitType | None:
        from app.models.property import Room
        ut = await self.get(unit_type_id)
        if not ut or ut.deleted_at is None:
            return None
        ut.deleted_at = None
        room_result = await self.session.execute(
            select(Room).where(Room.unit_type_id == unit_type_id, Room.deleted_at.isnot(None))
        )
        for r in room_result.scalars().all():
            r.deleted_at = None
            r.status = "available"
        await self.session.commit()
        await self.session.refresh(ut)
        await self._audit("恢复户型", unit_type_id, {"户型名": ut.name})
        return ut

    async def list_deleted(self, *, skip: int = 0, limit: int = 20, institute_id: int | None = None) -> dict:
        filters = [UnitType.deleted_at.isnot(None)]
        if institute_id is not None:
            filters.append(UnitType.institute_id == institute_id)
        base = select(func.count(UnitType.id))
        for f in filters: base = base.where(f)
        total = (await self.session.scalar(base)) or 0
        stmt = (select(UnitType)
                .options(selectinload(UnitType.institute), selectinload(UnitType.images))
                .order_by(UnitType.deleted_at.desc())
                .offset(skip).limit(limit))
        for f in filters: stmt = stmt.where(f)
        result = await self.session.scalars(stmt)
        items = list(result.unique())
        return {"items": items, "total": total, "page": skip // limit + 1, "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}
