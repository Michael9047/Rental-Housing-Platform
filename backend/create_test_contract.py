"""为 landlord1 创建已支付未签合同的测试 case"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.user import User
from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.payment import Payment, PaymentStatus
from app.models.unit_type import UnitType
from app.models.tenant import Tenant
from app.models.institute import Institute
from app.services.contract_service import ContractService
from app.services.lease_pricing_service import LeasePricingService


async def main():
    async with async_session_maker() as session:
        # 1. 找到 landlord1
        landlord = await session.scalar(select(User).where(User.username == "landlord1"))
        if not landlord:
            print("ERROR: landlord1 not found")
            # 列出所有用户
            users = (await session.scalars(select(User))).all()
            for u in users:
                print(f"  User: id={u.id} username={u.username} role={u.role}")
            return
        print(f"Found landlord1: id={landlord.id}, role={landlord.role}")

        # 2. 找一个可用的 unit_type 和 institute
        ut = await session.scalar(
            select(UnitType).options(selectinload(UnitType.institute)).where(UnitType.deleted_at.is_(None)).limit(1)
        )
        if not ut:
            print("ERROR: No unit_type found")
            return
        print(f"Found unit_type: id={ut.id} name={ut.name} institute_id={ut.institute_id}")

        # 3. 找到或创建一个 tenant (用 landlord1 自己作为 tenant user)
        tenant_user = landlord  # 用 landlord1 自己
        tenant = await session.scalar(select(Tenant).where(Tenant.user_id == tenant_user.id))
        if not tenant:
            tenant = Tenant(
                user_id=tenant_user.id,
                chinese_name=landlord.username,
                phone="13800000001",
            )
            session.add(tenant)
            await session.flush()
            print(f"Created tenant: id={tenant.id}")
        else:
            print(f"Found existing tenant: id={tenant.id}")

        # 4. 检查是否已有可用的 booking
        existing_booking = await session.scalar(
            select(Booking).where(
                Booking.user_id == tenant_user.id,
                Booking.status.in_([BookingStatus.payment_pending, BookingStatus.paid]),
            ).limit(1)
        )

        if existing_booking:
            print(f"Found existing booking: id={existing_booking.id} status={existing_booking.status}")

            # Check if already has a payment
            existing_payment = await session.scalar(
                select(Payment).where(Payment.booking_id == existing_booking.id).order_by(Payment.created_at.desc())
            )
            if existing_payment:
                print(f"  Existing payment: id={existing_payment.id} status={existing_payment.status}")

            # Check contract
            existing_contract = await session.scalar(
                select(Contract).where(Contract.booking_id == existing_booking.id).order_by(Contract.version.desc())
            )
            if existing_contract:
                print(f"  Existing contract: id={existing_contract.id} status={existing_contract.status}")

            use_booking = existing_booking
        else:
            # 5. 创建 booking
            now = datetime.now(timezone.utc)
            move_in = (now + timedelta(days=30)).strftime("%Y-%m-%d")

            booking = Booking(
                user_id=tenant_user.id,
                tenant_id=tenant.id,
                unit_type_id=ut.id,
                institute_id=ut.institute_id,
                bm_id=landlord.id,
                status=BookingStatus.payment_pending,
                scheduled_date=move_in,
                lease_months=12,
                deposit_amount=2000,
                service_fee=500,
                total_rent=24000,
                deposit_status="unpaid",
                payment_expires_at=now + timedelta(hours=24),
            )
            session.add(booking)
            await session.flush()
            print(f"Created booking: id={booking.id}")
            use_booking = booking

        # 6. 创建/更新 payment 为 success 状态
        now = datetime.now(timezone.utc)
        existing_payment = await session.scalar(
            select(Payment).where(Payment.booking_id == use_booking.id).order_by(Payment.created_at.desc())
        )

        if existing_payment and existing_payment.status == PaymentStatus.success:
            print(f"Payment already success: id={existing_payment.id}")
        else:
            if existing_payment:
                # Update existing payment to success
                existing_payment.status = PaymentStatus.success
                existing_payment.paid_at = now
                existing_payment.updated_at = now
                print(f"Updated existing payment to success: id={existing_payment.id}")
            else:
                # Create new payment
                payment = Payment(
                    booking_id=use_booking.id,
                    user_id=tenant_user.id,
                    order_id=f"PAY-TEST-{now:%Y%m%d}-{use_booking.id}",
                    payment_attempt_id=f"attempt-{use_booking.id}-{now.timestamp()}",
                    idempotency_key=f"test-{use_booking.id}-{now.timestamp()}",
                    amount=250000,  # 2500元 = 250000分
                    status=PaymentStatus.success,
                    settlement_currency="CNY",
                    settlement_amount_minor=250000,  # 2500元
                    cny_reference_amount_minor=250000,
                    property_currency="CNY",
                    exchange_rate_timestamp=now,
                    payment_method="card_checkout",
                    paid_at=now,
                    expires_at=now + timedelta(hours=24),
                    snapshot={
                        "order_number": str(use_booking.id),
                        "property_id": use_booking.institute_id,
                        "property_name": ut.name,
                        "property_address": ut.institute.address if ut.institute else "",
                        "commencement_date": use_booking.scheduled_date,
                        "tenancy_months": use_booking.lease_months,
                        "tenant_name": landlord.username,
                        "agreement_id": "",
                        "agreement_number": "",
                        "agreement_version": 1,
                        "fees": {
                            "deposit": {"currency": "CNY", "minor_units": 200000, "minor_unit_exponent": 2, "decimal": "2000.00"},
                            "service_fee": {"currency": "CNY", "minor_units": 50000, "minor_unit_exponent": 2, "decimal": "500.00"},
                            "current_total": {"currency": "CNY", "minor_units": 250000, "minor_unit_exponent": 2, "decimal": "2500.00"},
                            "tax": {"currency": "CNY", "minor_units": 0, "minor_unit_exponent": 2, "decimal": "0.00"},
                        },
                    },
                )
                session.add(payment)
                await session.flush()
                print(f"Created payment: id={payment.id} status=success")

        # 7. 更新 booking 状态为 paid
        if use_booking.status != BookingStatus.paid:
            use_booking.status = BookingStatus.paid
            print(f"Updated booking status to: paid")

        # 8. 确保有未签署的合同
        existing_contract = await session.scalar(
            select(Contract).where(Contract.booking_id == use_booking.id).order_by(Contract.version.desc())
        )

        if existing_contract:
            if existing_contract.status == "signed":
                # 创建一个新版本的未签署合同
                contract = Contract(
                    booking_id=use_booking.id,
                    tenant_id=tenant_user.id,
                    unit_type_id=use_booking.unit_type_id,
                    template_name="housing_reservation_tenancy_bilingual",
                    agreement_number=f"TEST-{use_booking.id}-v{existing_contract.version + 1}",
                    version=existing_contract.version + 1,
                    template_version="housing-2026.1",
                    content_hash="test_hash_unsigned",
                    snapshot=existing_contract.snapshot or {},
                    content=existing_contract.content or "Test contract content",
                    status="generated",
                    generated_at=now,
                )
                session.add(contract)
                await session.flush()
                print(f"Created new unsigned contract: id={contract.id} status=generated")
            else:
                print(f"Existing contract already unsigned: id={existing_contract.id} status={existing_contract.status}")
        else:
            # 创建合同
            contract = Contract(
                booking_id=use_booking.id,
                tenant_id=tenant_user.id,
                unit_type_id=use_booking.unit_type_id,
                template_name="housing_reservation_tenancy_bilingual",
                agreement_number=f"TEST-{use_booking.id}",
                version=1,
                template_version="housing-2026.1",
                content_hash="test_hash_new",
                snapshot={
                    "tenant_name_cn": landlord.username,
                    "tenant_name_en": landlord.username,
                    "provider_name": ut.institute.name if ut.institute else "Test Institute",
                    "platform_name": "XJTLU Rental Platform",
                    "platform_role": "中介服务平台",
                    "property_name": ut.name,
                    "property_id": str(ut.id),
                    "property_address": ut.institute.address if ut.institute else "Test Address",
                    "room_type": str(getattr(ut, 'property_type', 'studio')),
                    "commencement_date": use_booking.scheduled_date,
                    "expiry_date": "2027-07-01",
                    "tenancy_months": use_booking.lease_months or 12,
                    "monthly_rent": "2000.00 CNY",
                    "deposit": "2000.00 CNY",
                    "service_fee": "500.00 CNY",
                    "amount_due_now": "2500.00 CNY",
                    "future_rent": "24000.00 CNY",
                    "tax_treatment": "已包含在租金中",
                    "utilities": {"zh": "租客自付", "en": "Tenant pays"},
                },
                content="租赁合同测试内容 - 待签署",
                status="generated",
                generated_at=now,
            )
            session.add(contract)
            await session.flush()
            print(f"Created contract: id={contract.id} status=generated")

        await session.commit()
        print("\n=== 测试数据创建完成 ===")
        print(f"Landlord: {landlord.username} (id={landlord.id})")
        print(f"Booking:  id={use_booking.id} status={use_booking.status.value}")

        # Re-query payment and contract to confirm
        final_payment = await session.scalar(
            select(Payment).where(Payment.booking_id == use_booking.id).order_by(Payment.created_at.desc())
        )
        final_contract = await session.scalar(
            select(Contract).where(Contract.booking_id == use_booking.id).order_by(Contract.version.desc())
        )
        print(f"Payment:  id={final_payment.id if final_payment else 'N/A'} status={final_payment.status.value if final_payment else 'N/A'}")
        print(f"Contract: id={final_contract.id if final_contract else 'N/A'} status={final_contract.status if final_contract else 'N/A'}")
        print(f"\n合约签署测试入口: GET /api/v1/contracts/my/{final_contract.id if final_contract else 'N/A'}")


if __name__ == "__main__":
    asyncio.run(main())
