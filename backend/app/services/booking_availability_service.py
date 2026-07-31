"""户型可用性检查服务（UnitType 中心）。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.property_service import PropertyService


class BookingAvailabilityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_unit_type(self, unit_type_id: int):
        """获取户型对象（原 get_property 改名，保持兼容）。"""
        return await PropertyService(self.session).get(unit_type_id)

    async def get_property(self, unit_type_id: int):
        """兼容旧调用 — 等同于 get_unit_type。"""
        return await self.get_unit_type(unit_type_id)

    async def validate(self, unit_type, move_in_date: str):
        """验证户型是否可预订。unit_type 为 UnitType 模型实例。返回 (valid, reason, detail)。"""
        if not unit_type:
            return False, "户型不存在", None
        if not move_in_date:
            return False, "请选择起租日期", None
        # 检查是否有空房
        if not getattr(unit_type, "has_vacancy", True):
            return False, "该户型已满", None
        if getattr(unit_type, "available_count", 1) <= 0:
            return False, "该户型已无剩余房间", None
        return True, "", None
