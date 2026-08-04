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
    """将上传的图片关联到户型，生成唯一文件名。优先从 temp 移动，若已移动则从根目录复制。"""
    from app.core.config import get_settings
    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    result = []
    for url in urls:
        old_fn = url.rsplit("/", 1)[-1] if "/" in url else url
        ext = Path(old_fn).suffix or ".png"
        new_fn = f"{_uuid.uuid4().hex}{ext}"
        found = False

        # 1) 尝试从 temp 目录移动
        if "/temp/" in url and "/api/v1/uploads/" in url:
            rel = url.split("/api/v1/uploads/", 1)[-1]
            src = upload_root / rel
            if src.exists():
                try:
                    shutil.move(str(src), str(upload_root / new_fn))
                    found = True
                except Exception:
                    pass

        # 2) temp 不存在，尝试从根目录找（之前失败的提交可能已经移动了文件）
        if not found:
            root_src = upload_root / old_fn
            if root_src.exists():
                try:
                    shutil.copy2(str(root_src), str(upload_root / new_fn))
                    found = True
                except Exception:
                    pass

        result.append(new_fn)
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
            rental_requirements=data.rental_requirements,
            currency=data.currency, special_offer=data.special_offer,
            floor_pricing=data.floor_pricing, amenities=data.amenities,
            description=data.description,
            available_from=data.available_from, min_stay_months=data.min_stay_months,
            status=data.status,
        )
        self.session.add(ut)
        await self.session.flush()

        # 处理图片：从 image_urls 创建 UnitTypeImage 记录
        image_urls = getattr(data, 'image_urls', None) or []
        if image_urls:
            permanent = _move_temp_images(image_urls)
            for idx, fn in enumerate(permanent):
                img = UnitTypeImage(
                    unit_type_id=ut.id, filename=fn, original_name=fn,
                    mime_type='image/jpeg', file_size=0,
                    sort_order=idx, is_primary=(idx == 0),
                )
                self.session.add(img)

        await self.session.commit()
        await self.session.refresh(ut)

        from app.models.institute import Institute
        inst = await self.session.get(Institute, ut.institute_id)
        inst_name = inst.name if inst else ""
        desc = f"在「{inst_name}」公寓下创建了户型「{ut.name}」（{ut.bedrooms}室{ut.hall_count}厅{ut.bathrooms}卫，{ut.area_sqm}㎡，¥{ut.base_rent}/月）"
        await self._audit("创建户型", ut.id, {"描述": desc, "户型名": ut.name, "公寓": inst_name, "月租": str(ut.base_rent)})

        if ut.institute_id:
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
        # Room 表已删除（三层改两层），不再计算 room_count
        return {"items": items, "total": total, "page": skip // limit + 1, "page_size": limit, "total_pages": max(1, (total + limit - 1) // limit)}

    async def update(self, unit_type_id: int, data: UnitTypeUpdate) -> UnitType | None:
        ut = await self.get(unit_type_id)
        if not ut: return None
        update_data = data.model_dump(exclude_unset=True)
        # image_urls 不映射到模型列，单独处理
        image_urls = update_data.pop('image_urls', None)
        old_vals = {k: str(getattr(ut, k, '') or '') for k in update_data}
        for k, v in update_data.items(): setattr(ut, k, v)
        await self.session.flush()

        if image_urls is not None:
            # 删除旧图片记录
            from sqlalchemy import delete as _delete
            await self.session.execute(_delete(UnitTypeImage).where(UnitTypeImage.unit_type_id == unit_type_id))
            # 创建新图片记录
            if image_urls:
                permanent = _move_temp_images(image_urls)
                for idx, fn in enumerate(permanent):
                    img = UnitTypeImage(
                        unit_type_id=ut.id, filename=fn, original_name=fn,
                        mime_type='image/jpeg', file_size=0,
                        sort_order=idx, is_primary=(idx == 0),
                    )
                    self.session.add(img)

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
        """软删除户型（两层架构不再有下属房间）"""
        from datetime import datetime
        ut = await self.get(unit_type_id)
        if not ut: return False
        name = ut.name
        ut.deleted_at = datetime.utcnow()
        await self.session.commit()
        await self._audit("删除户型", unit_type_id, {"户型名": name})
        return True

    async def restore(self, unit_type_id: int) -> UnitType | None:
        """恢复已删除的户型"""
        ut = await self.get(unit_type_id)
        if not ut or ut.deleted_at is None:
            return None
        ut.deleted_at = None
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
