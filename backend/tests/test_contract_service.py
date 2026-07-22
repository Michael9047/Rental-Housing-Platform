"""电子合同房源快照与正式合同文本测试。"""

from decimal import Decimal

import pytest

from app.models.booking import Booking
from app.models.property import (
    CountryCode,
    DepositType,
    Property,
    PropertyType,
    RentType,
)
from app.models.user import User, UserRole
from app.services.contract_service import ContractService
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_generate_contract_captures_complete_property_snapshot(
    session_maker,
    monkeypatch,
) -> None:
    async def ignore_notification(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        NotificationService,
        "create_notification",
        ignore_notification,
    )

    async with session_maker() as session:
        landlord = User(
            username="测试房东",
            email="contract-landlord@example.com",
            role=UserRole.landlord,
        )
        tenant = User(
            username="测试租客",
            email="contract-tenant@example.com",
            role=UserRole.tenant,
        )
        session.add_all([landlord, tenant])
        await session.flush()

        property_obj = Property(
            landlord_id=landlord.id,
            title="滨江两居室",
            description="采光良好，步行可达地铁与超市。",
            address="测试市滨江路 88 号",
            district="滨江区",
            country=CountryCode.CN,
            price_monthly=Decimal("6200.00"),
            area_sqm=Decimal("72.50"),
            bedrooms=2,
            bathrooms=1,
            property_type=PropertyType.apartment,
            floor=12,
            room_number="1208",
            amenities=["电梯", "空调", "洗衣机"],
            min_lease_months=6,
            max_lease_months=24,
            rent_type=RentType.monthly,
            deposit_amount=6200,
            deposit_type=DepositType.one_month,
            service_fee_rate=0.05,
        )
        session.add(property_obj)
        await session.flush()

        booking = Booking(
            tenant_id=tenant.id,
            landlord_id=landlord.id,
            property_id=property_obj.id,
            scheduled_date="2026-08-15",
            lease_months=12,
            total_rent=74400,
            deposit_amount=6200,
            service_fee=310,
        )
        session.add(booking)
        await session.commit()
        await session.refresh(booking)

        contract = await ContractService(session).generate_contract(booking)

        assert contract.template_name == "standard_lease_v2"
        assert contract.property_snapshot is not None
        assert contract.property_snapshot["title"] == "滨江两居室"
        assert contract.property_snapshot["price_monthly"] == 6200
        assert contract.property_snapshot["area_sqm"] == 72.5
        assert contract.property_snapshot["amenities"] == ["电梯", "空调", "洗衣机"]
        assert contract.property_snapshot["source"] == "platform_property_database"
        assert "测试市滨江路 88 号" in contract.content
        assert "2 室 1 卫" in contract.content
        assert "2026年08月15日" in contract.content
        assert "2027年08月14日" in contract.content
        assert "人民币 74,400.00 元" in contract.content
        assert "电梯、空调、洗衣机" in contract.content
        assert await ContractService(session).list_by_booking(booking.id) == contract

        with pytest.raises(ValueError, match="Contract already exists"):
            await ContractService(session).generate_contract(booking)
