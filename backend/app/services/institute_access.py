"""公寓管理范围的统一权限判断，供楼栋与合同模板接口复用。"""

from sqlalchemy import and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institute import Institute
from app.models.user import User, UserRole


def managed_institute_filter(current_user: User):
    """返回当前用户可管理公寓的查询条件，管理员返回全部。"""
    if current_user.role == UserRole.admin:
        return None
    if current_user.role != UserRole.landlord:
        return false()
    return or_(
        Institute.bm_id == current_user.id,
        and_(
            Institute.bm_id.is_(None),
            Institute.created_by == current_user.id,
        ),
    )


async def can_manage_institute(
    session: AsyncSession, current_user: User, institute_id: int
) -> bool:
    """确认用户可管理指定公寓，历史自建且未分配 BM 的数据保持兼容。"""
    stmt = select(Institute.id).where(Institute.id == institute_id)
    scope = managed_institute_filter(current_user)
    if scope is not None:
        stmt = stmt.where(scope)
    return await session.scalar(stmt) is not None
