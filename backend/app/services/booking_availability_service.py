"""房源可用性检查服务。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.property_service import PropertyService


class BookingAvailabilityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_property(self, property_id: int):
        """获取房源对象。"""
        return await PropertyService(self.session).get(property_id)

    async def validate(self, property_obj, move_in_date: str):
        """验证房源是否可预订。返回 (valid, reason, detail)。"""
        if not property_obj:
            return False, "房源不存在", None
        if not move_in_date:
            return False, "请选择起租日期", None
        return True, "", None
