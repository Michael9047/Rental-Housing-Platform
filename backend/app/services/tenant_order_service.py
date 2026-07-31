"""已废弃 — Order 表已删除。保留兼容导入。"""
from app.models._compat import Order


class TenantOrderService:
    """兼容占位 — Order 表已删除。"""
    def __init__(self, session):
        self.session = session

    async def list_by_tenant(self, tenant_id: int):
        return []

    async def list_all(self):
        return []

    async def get(self, order_id: int):
        return None
