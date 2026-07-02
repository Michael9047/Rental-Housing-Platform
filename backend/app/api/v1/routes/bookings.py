from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_landlord, require_tenant
from app.models.booking import BookingStatus
from app.models.user import User, UserRole
from app.schemas.booking import BookingContractInfoUpdate, BookingCreate, BookingRead, BookingUpdate
from app.services.booking_service import BookingService
from app.services.contract_service import ContractService
from app.services.property_service import PropertyService

router = APIRouter()


def _contract_info_complete(booking: object) -> bool:
    return all(
        getattr(booking, field, None)
        for field in (
            "contract_real_name",
            "contract_id_card_no",
            "contract_phone",
            "lease_start_date",
            "lease_end_date",
        )
    )


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_in: BookingCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingRead:
    if booking_in.message is None and booking_in.scheduled_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of message or scheduled_date is required",
        )

    property_obj = await PropertyService(session).get(booking_in.property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    booking_service = BookingService(session)
    try:
        booking = await booking_service.create_booking(
            tenant_id=current_user.id,
            property_id=booking_in.property_id,
            landlord_id=property_obj.landlord_id,
            booking_in=booking_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return booking


@router.get("", response_model=list[BookingRead])
async def list_bookings(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[BookingRead]:
    booking_service = BookingService(session)
    if current_user.role in {UserRole.landlord, UserRole.admin}:
        return await booking_service.list_by_landlord(current_user.id)
    return await booking_service.list_by_tenant(current_user.id)


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    booking = await BookingService(session).get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id not in {booking.tenant_id, booking.landlord_id} and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return booking


@router.patch("/{booking_id}/status", response_model=BookingRead)
async def update_booking_status(
    booking_id: int,
    update_in: BookingUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> BookingRead:
    if update_in.status not in {BookingStatus.approved, BookingStatus.rejected, BookingStatus.completed}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be approved, rejected, or completed",
        )

    booking_service = BookingService(session)
    booking = await booking_service.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != booking.landlord_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the landlord can update this booking")

    if update_in.status == BookingStatus.completed and booking.status != BookingStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved bookings can be marked completed",
        )

    updated = await booking_service.update_status(booking_id, update_in.status)
    return updated


@router.patch("/{booking_id}/contract-info", response_model=BookingRead)
async def update_contract_info(
    booking_id: int,
    info_in: BookingContractInfoUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingRead:
    booking_service = BookingService(session)
    booking = await booking_service.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != booking.tenant_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the tenant can submit contract info")

    if booking.status in {BookingStatus.cancelled, BookingStatus.rejected}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot update contract info for inactive booking")

    existing_contract = await ContractService(session).list_by_booking(booking_id)
    if existing_contract:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contract has already been generated")

    updated = await booking_service.update_contract_info(booking_id, info_in)
    return updated


@router.patch("/{booking_id}/contract-info/confirm", response_model=BookingRead)
async def confirm_contract_info(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> BookingRead:
    booking_service = BookingService(session)
    booking = await booking_service.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != booking.landlord_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the landlord can confirm contract info")

    if not _contract_info_complete(booking):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contract info is incomplete")

    if booking.contract_info_status != "pending_landlord":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contract info is not waiting for landlord confirmation")

    updated = await booking_service.confirm_contract_info(booking_id)
    return updated


@router.patch("/{booking_id}/cancel", response_model=BookingRead)
async def cancel_booking(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingRead:
    booking_service = BookingService(session)
    booking = await booking_service.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != booking.tenant_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the tenant can cancel this booking")

    updated = await booking_service.update_status(booking_id, BookingStatus.cancelled)
    return updated
