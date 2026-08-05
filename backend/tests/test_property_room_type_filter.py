"""房源房型筛选兼容当前三层数据结构的回归测试。"""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.property import Property
from app.models.room_type import RoomType as LegacyRoomType
from app.services.property_service import PropertyService


def test_legacy_room_type_foreign_key_targets_properties() -> None:
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in LegacyRoomType.__table__.c.property_id.foreign_keys
    }

    assert foreign_keys == {"properties.id"}


def test_room_type_filter_uses_unit_types_instead_of_removed_table() -> None:
    statement = select(Property.id).where(
        PropertyService._room_type_filter_clause("ensuite")
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "unit_types" in sql
    assert "properties.unit_type_id" in sql
    assert "room_types" not in sql
