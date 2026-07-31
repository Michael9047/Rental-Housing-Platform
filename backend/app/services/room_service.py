"""已废弃 — Room 表已删除。保留兼容导入。"""


class RoomService:
    """兼容占位 — Room 表已删除。"""
    def __init__(self, session):
        self.session = session

    async def create(self, data):
        raise NotImplementedError("Room table deleted — use UnitType")

    async def get(self, room_id):
        return None

    async def list(self, **filters):
        return [], 0

    async def update(self, room_id, data):
        raise NotImplementedError("Room table deleted")

    async def soft_delete(self, room_id):
        raise NotImplementedError("Room table deleted")

    async def restore(self, room_id):
        raise NotImplementedError("Room table deleted")

    async def hard_delete(self, room_id):
        raise NotImplementedError("Room table deleted")
