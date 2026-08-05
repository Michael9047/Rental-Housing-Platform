"""公开房源详情接口回归测试。"""

from sqlalchemy.dialects import postgresql

from app.main import _public_room_statement


def test_public_room_detail_reads_properties_table() -> None:
    statement = _public_room_statement(4)
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FROM properties" in sql
    assert "FROM rooms" not in sql
