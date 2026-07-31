"""已废弃 — RoomType 表已删除，已被 UnitTypeService 替代。保留兼容导入。"""


class RoomTypeService:
    """兼容占位 — RoomType 表已删除。"""
    def __init__(self, session):
        self.session = session

    async def list_by_property(self, property_id: int):
        return []

    async def get(self, room_type_id: int):
        return None

    async def create(self, data):
        raise NotImplementedError("RoomType table deleted — use UnitType")

    async def update(self, room_type_id, data):
        raise NotImplementedError("RoomType table deleted — use UnitType")

    async def delete(self, room_type_id):
        raise NotImplementedError("RoomType table deleted — use UnitType")
