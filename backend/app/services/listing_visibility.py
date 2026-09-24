"""集中定义面向租客的新搜索与新预订可售规则。"""
from sqlalchemy import and_

from app.models.institute import Institute, InstituteStatus
from app.models.unit_type import UnitType, UnitTypeStatus


def listable_clause():
    """返回适用于 UnitType JOIN Institute 查询的统一 SQL 条件。"""
    return and_(
        UnitType.status == UnitTypeStatus.available,
        UnitType.deleted_at.is_(None),
        UnitType.has_vacancy.is_(True),
        UnitType.available_count > 0,
        Institute.status == InstituteStatus.active,
    )


def is_listable(unit_type: UnitType) -> bool:
    """判断已加载公寓关联的户型能否用于新搜索或新预订。"""
    institute = unit_type.institute
    return bool(
        unit_type.status == UnitTypeStatus.available
        and unit_type.deleted_at is None
        and unit_type.has_vacancy
        and unit_type.available_count > 0
        and institute is not None
        and institute.status == InstituteStatus.active
    )
