import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_tenant
from app.models.notification import NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.booking_service import BookingService
from app.services.notification_service import NotificationService

router = APIRouter()


@router.post("/create", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_in: PaymentCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> PaymentResponse:
    booking = await BookingService(session).get(payment_in.booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != booking.tenant_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the tenant can create payment")

    payment = Payment(
        id=str(uuid.uuid4()),
        booking_id=payment_in.booking_id,
        user_id=current_user.id,
        amount=payment_in.amount,
        out_trade_no=str(uuid.uuid4()).replace("-", ""),
        status=PaymentStatus.pending,
        payment_method="wechat_pay",
    )
    session.add(payment)

    # Update booking deposit_status to "paid" when payment is created
    booking.deposit_status = "paid"
    booking.payment_transaction_id = payment.transaction_id

    await session.commit()
    await session.refresh(payment)

    # 通知租客
    notification_service = NotificationService(session)
    await notification_service.create_notification(
        user_id=current_user.id,
        type=NotificationType.payment_created,
        title="支付已发起",
        content=f"您对预约 #{booking.id} 的支付已发起，金额 ¥{payment.amount / 100:.2f}",
        channels=["email"],
    )
    # 通知房东
    await notification_service.create_notification(
        user_id=booking.landlord_id,
        type=NotificationType.payment_created,
        title="租客已发起支付",
        content=f"租客已对预约 #{booking.id} 发起支付，金额 ¥{payment.amount / 100:.2f}",
        channels=["email"],
    )

    return payment


@router.post("/{payment_id}/callback", response_model=PaymentResponse)
async def payment_callback(
    payment_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> PaymentResponse:
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    # Simulate payment callback - in production validate WeChat callback signature
    payment.status = PaymentStatus.success
    payment.paid_at = datetime.utcnow()

    # Update booking status
    booking = await BookingService(session).get(payment.booking_id)
    if booking:
        booking.deposit_status = "confirmed"

    await session.commit()
    await session.refresh(payment)

    # 通知租客和房东
    notification_service = NotificationService(session)
    await notification_service.create_notification(
        user_id=payment.user_id,
        type=NotificationType.payment_received,
        title="支付到账",
        content=f"您对预约 #{payment.booking_id} 的支付 ¥{payment.amount / 100:.2f} 已到账",
        channels=["email"],
    )
    if booking:
        await notification_service.create_notification(
            user_id=booking.landlord_id,
            type=NotificationType.payment_received,
            title="收到支付",
            content=f"预约 #{payment.booking_id} 的支付 ¥{payment.amount / 100:.2f} 已到账，请确认",
            channels=["email"],
        )

    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PaymentResponse:
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if current_user.id != payment.user_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return payment
