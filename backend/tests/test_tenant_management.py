"""BM 租客管理查询与订单回填规则测试。"""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.api.v1.routes.tenants import (
    TENANT_BOOKING_STATUSES,
    _managed_tenant_by_id_statement,
    _managed_tenant_statement,
    _to_read,
)
from app.models.booking import BookingStatus
from app.models.user import UserRole


def test_signed_and_completed_bookings_are_visible_as_tenants() -> None:
    assert TENANT_BOOKING_STATUSES == {
        BookingStatus.contract_signed,
        BookingStatus.completed,
    }


def test_bm_tenant_query_uses_direct_and_institute_scope() -> None:
    statement = _managed_tenant_statement(
        SimpleNamespace(id=42, role=UserRole.landlord)
    )
    sql = str(statement)
    assert "bookings.bm_id" in sql
    assert "institutes.bm_id" in sql


def test_single_tenant_query_keeps_management_scope() -> None:
    statement = _managed_tenant_by_id_statement(
        SimpleNamespace(id=42, role=UserRole.landlord), tenant_id=9
    )
    sql = str(statement)
    assert "tenants.id" in sql
    assert "bookings.bm_id" in sql
    assert "institutes.bm_id" in sql


@pytest.mark.asyncio
async def test_single_tenant_endpoint_requires_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/tenants/1")
    assert response.status_code == 401


def test_booking_housing_data_fills_tenant_list_row() -> None:
    institute = SimpleNamespace(name="测试公寓")
    unit_type = SimpleNamespace(id=8, name="Studio", institute=institute)
    tenant = SimpleNamespace(
        id=1, user_id=2, is_default=False, surname_pinyin="LI",
        given_name_pinyin="Ming", chinese_name="李明", phone="123",
        email=None, school_name="XJTLU", current_unit_type_id=None,
        unit_type=None, room_number=None, housing_status="active",
        move_in_date=None, move_out_date=None, label=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )
    booking = SimpleNamespace(
        unit_type=unit_type, unit_type_id=8, institute=institute,
        room_number="A-301", contract_start=date(2026, 9, 1),
        contract_end=date(2027, 8, 31), scheduled_date=None, lease_months=12,
    )

    row = _to_read(tenant, booking)

    assert row.current_unit_type_id == 8
    assert row.institute_name == "测试公寓"
    assert row.room_number == "A-301"
    assert row.move_in_date == date(2026, 9, 1)
