"""购物车服务 —— 候选清单 CRUD（纯工具，非 Agent）

供 API 路由、ToolRegistry handler、CompareAgent 直接调用。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_cart import AgentCart, AgentCartItem
from app.models.property import Property


class CartService:
    """购物车 CRUD 服务。持 DB session，所有方法为纯数据库操作，零 LLM 调用。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_cart(self, user_id: int) -> AgentCart:
        """获取或创建用户的购物车（最新的一条）。"""
        stmt = (
            select(AgentCart)
            .where(AgentCart.user_id == user_id)
            .order_by(AgentCart.created_at.desc())
        )
        cart = (await self.session.scalars(stmt)).first()
        if cart is None:
            cart = AgentCart(user_id=user_id)
            self.session.add(cart)
            await self.session.commit()
            await self.session.refresh(cart)
        return cart

    async def add_to_cart(
        self, user_id: int, property_id: int, reason: str | None = None
    ) -> AgentCartItem:
        """加入购物车；重复添加返回已有项。"""
        prop = await self.session.get(Property, property_id)
        if prop is None:
            raise ValueError("房源不存在")

        cart = await self.get_or_create_cart(user_id)
        stmt = select(AgentCartItem).where(
            AgentCartItem.cart_id == cart.id,
            AgentCartItem.property_id == property_id,
        )
        existing = (await self.session.scalars(stmt)).first()
        if existing is not None:
            return existing

        item = AgentCartItem(cart_id=cart.id, property_id=property_id, reason=reason)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_from_cart(self, user_id: int, property_id: int) -> bool:
        """从购物车移除房源。返回是否实际删除了记录。"""
        cart = await self.get_or_create_cart(user_id)
        stmt = select(AgentCartItem).where(
            AgentCartItem.cart_id == cart.id,
            AgentCartItem.property_id == property_id,
        )
        item = (await self.session.scalars(stmt)).first()
        if item is None:
            return False
        await self.session.delete(item)
        await self.session.commit()
        return True

    async def get_cart_items(self, user_id: int) -> tuple[AgentCart, list[AgentCartItem]]:
        """获取购物车及其中所有条目（按添加时间升序）。"""
        cart = await self.get_or_create_cart(user_id)
        stmt = (
            select(AgentCartItem)
            .where(AgentCartItem.cart_id == cart.id)
            .order_by(AgentCartItem.created_at.asc())
        )
        items = list(await self.session.scalars(stmt))
        return cart, items
