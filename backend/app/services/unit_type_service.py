"""户型服务层"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.institute import Institute, InstituteStatus
from app.models.unit_type import UnitType, UnitTypeStatus
from app.models.user import User, UserRole
from app.models.booking import Booking, BookingStatus
from app.models.audit_log import AuditLog
from app.schemas.unit_type import UnitTypeCreate, UnitTypeUpdate
from app.services.institute_access import managed_institute_filter


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
        ut = UnitType(
            institute_id=data.institute_id, name=data.name,
            property_type=data.property_type,
            bedrooms=data.bedrooms, bathrooms=data.bathrooms, hall_count=data.hall_count,
            area_sqm=data.area_sqm, base_rent=data.base_rent,
            rent_period=data.rent_period or "monthly",
            deposit_amount=data.deposit_amount, deposit_type=data.deposit_type,
            lease_start=data.lease_start, lease_end=data.lease_end,
            currency=data.currency, special_offer=data.special_offer,
            floor_pricing=data.floor_pricing, amenities=data.amenities,
            image_urls=data.image_urls, description=data.description,
            available_from=data.available_from, min_stay_months=data.min_stay_months,
            total_count=data.total_count, available_count=data.available_count,
            has_vacancy=data.has_vacancy,
            status=data.status,
        )
        self.session.add(ut)
        await self.session.commit()
        await self.session.refresh(ut)
        inst_name = ""
        try:
            from app.models.institute import Institute
            inst = await self.session.get(Institute, ut.institute_id)
            inst_name = inst.name if inst else ""
        except Exception: pass
        rp_label = data.rent_period or "monthly"
        unit_label = "/周" if rp_label == "weekly" else "/月"
        desc = f"在「{inst_name}」公寓下创建了户型「{ut.name}」"
        desc += f"（{ut.bedrooms}室{ut.hall_count}厅{ut.bathrooms}卫，{ut.area_sqm}㎡，¥{ut.base_rent}{unit_label}）"
        await self._audit("创建户型", ut.id, {"描述": desc, "户型名": ut.name, "公寓": inst_name, "租金": str(ut.base_rent), "租金周期": rp_label})
        # 预加载 institute 名称（避免 _to_read 的 MissingGreenlet）
        from app.models.institute import Institute
        if ut.institute_id:
            inst = await self.session.get(Institute, ut.institute_id)
            ut._institute_name = inst.name if inst else None
            ut._institute_business_id = inst.business_id if inst else None
        return ut

    async def get(self, unit_type_id: int) -> UnitType | None:
        return await self.session.get(UnitType, unit_type_id, options=[selectinload(UnitType.institute)])

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        institute_id: int | None = None,
        current_user: User | None = None,
    ) -> dict:
        """列出户型；BM 看管理范围，游客与租客仅看已公开房源。"""
        filters = [UnitType.deleted_at.is_(None)]  # 排除已删除
        if institute_id is not None:
            filters.append(UnitType.institute_id == institute_id)
        is_manager = current_user is not None and current_user.role in {UserRole.landlord, UserRole.admin}
        if is_manager:
            scope = managed_institute_filter(current_user)
            if scope is not None:
                filters.append(scope)
        else:
            filters.extend((
                UnitType.status == UnitTypeStatus.available,
                Institute.status == InstituteStatus.active,
            ))
        base = select(func.count(UnitType.id)).join(Institute, Institute.id == UnitType.institute_id)
        for f in filters: base = base.where(f)
        total = (await self.session.scalar(base)) or 0
        stmt = (select(UnitType)
                .join(Institute, Institute.id == UnitType.institute_id)
                .options(selectinload(UnitType.institute))
                .order_by(UnitType.created_at.desc()).offset(skip).limit(limit))
        for f in filters: stmt = stmt.where(f)
        result = await self.session.scalars(stmt)
        items = list(result.unique())
        active_statuses = [
            BookingStatus.contract_signed, BookingStatus.payment_pending,
            BookingStatus.payment_processing, BookingStatus.paid,
        ]
        if items:
            rented_rows = await self.session.execute(
                select(Booking.unit_type_id, func.count(Booking.id)).where(
                    Booking.unit_type_id.in_([item.id for item in items]),
                    Booking.status.in_(active_statuses),
                ).group_by(Booking.unit_type_id)
            )
            rented_by_unit = dict(rented_rows.all())
            for item in items:
                item._rented_count = min(item.total_count, int(rented_by_unit.get(item.id, 0)))
        return {"items": items, "total": total, "page": skip // limit + 1, "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}

    async def update(self, unit_type_id: int, data: UnitTypeUpdate) -> UnitType | None:
        ut = await self.get(unit_type_id)
        if not ut: return None
        update_data = data.model_dump(exclude_unset=True)
        next_total = update_data.get("total_count", ut.total_count)
        next_available = update_data.get("available_count", ut.available_count)
        if next_available > next_total:
            raise ValueError("可租套数不能大于总套数")
        old_vals = {k: str(getattr(ut, k, '') or '') for k in update_data}
        for k, v in update_data.items(): setattr(ut, k, v)
        await self.session.commit()
        # refresh 恢复所有列属性（避免 MissingGreenlet），然后手填 institute 关系
        await self.session.refresh(ut)
        from app.models.institute import Institute
        inst = await self.session.get(Institute, ut.institute_id)
        ut._institute_name = inst.name if inst else None
        ut._institute_business_id = inst.business_id if inst else None
        changes = {k: {"新值": str(v), "旧值": old_vals.get(k, '')} for k, v in update_data.items()}
        await self._audit("编辑户型", ut.id, {"户型名": ut.name, "修改内容": changes})
        return ut

    async def delete(self, unit_type_id: int) -> bool:
        """级联软删除：户型 → 下属所有房间"""
        from datetime import datetime
        from app.models.property import Room
        ut = await self.get(unit_type_id)
        if not ut: return False
        name = ut.name
        now = datetime.utcnow()
        # Room 表已删除，不再有级联房间概念
        rooms: list = []
        # 软删除户型本身
        ut.deleted_at = now
        await self.session.commit()
        await self._audit("删除户型", unit_type_id, {"户型名": name, "级联删除房间": len(rooms)})
        return True

    async def restore(self, unit_type_id: int) -> UnitType | None:
        """级联恢复：户型 + 下属所有房间"""
        from app.models.property import Room
        ut = await self.get(unit_type_id)
        if not ut or ut.deleted_at is None:
            return None
        ut.deleted_at = None
        # Room 表已删除，不再有级联房间概念，仅恢复户型本身
        rooms: list = []
        for r in rooms:
            r.deleted_at = None
            r.status = "available"
        await self.session.commit()
        await self.session.refresh(ut)
        await self._audit("恢复户型", unit_type_id, {"户型名": ut.name, "恢复房间": len(rooms)})
        return ut

    async def list_deleted(
        self,
        *,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        institute_id: int | None = None,
    ) -> dict:
        """回收站列表 — 已删除的户型"""
        filters = [UnitType.deleted_at.isnot(None)]
        if institute_id is not None:
            filters.append(UnitType.institute_id == institute_id)
        scope = managed_institute_filter(current_user)
        if scope is not None:
            filters.append(scope)
        base = select(func.count(UnitType.id)).join(Institute, Institute.id == UnitType.institute_id)
        for f in filters: base = base.where(f)
        total = (await self.session.scalar(base)) or 0
        stmt = (select(UnitType)
                .join(Institute, Institute.id == UnitType.institute_id)
                .options(selectinload(UnitType.institute))
                .order_by(UnitType.deleted_at.desc())
                .offset(skip).limit(limit))
        for f in filters: stmt = stmt.where(f)
        result = await self.session.scalars(stmt)
        items = list(result.unique())
        return {"items": items, "total": total, "page": skip // limit + 1, "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}
