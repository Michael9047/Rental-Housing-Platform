from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_landlord, require_tenant
from app.models.booking import BookingStatus
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.schemas.booking_personal_info import BookingPersonalInfoValidation, BookingPersonalInfoValidationRead
from app.schemas.booking_emergency_contact import BookingEmergencyContactValidation, BookingEmergencyContactValidationRead
from app.schemas.policy import BookingConfirmationCreate, BookingConfirmationRead
from app.models.booking import Booking
from app.models.policy_consent import PolicyConsent
from app.models.booking_flow_draft import BookingFlowDraft
from app.schemas.booking_flow_draft import BookingFlowDraftRead, BookingFlowDraftUpdate
from app.services.booking_availability_service import BookingAvailabilityService
from app.services.lease_pricing_service import LeasePricingService
from app.services.policy_service import POLICIES
from app.services.booking_service import BookingService
from app.services.property_service import PropertyService

router = APIRouter()


@router.get("/drafts/{property_id}", response_model=BookingFlowDraftRead)
async def get_booking_flow_draft(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingFlowDraftRead:
    draft = await session.scalar(select(BookingFlowDraft).where(
        BookingFlowDraft.user_id == current_user.id,
        BookingFlowDraft.property_id == property_id,
    ))
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking draft not found")
    return draft


@router.put("/drafts/{property_id}", response_model=BookingFlowDraftRead)
async def save_booking_flow_draft(
    property_id: int,
    update: BookingFlowDraftUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingFlowDraftRead:
    property_obj = await PropertyService(session).get(property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    draft = await session.scalar(select(BookingFlowDraft).where(
        BookingFlowDraft.user_id == current_user.id,
        BookingFlowDraft.property_id == property_id,
    ))
    if not draft:
        draft = BookingFlowDraft(user_id=current_user.id, property_id=property_id)
        session.add(draft)
    payload = update.model_dump(exclude_unset=True)
    if update.personal_info is not None:
        payload["personal_info"] = update.personal_info.model_dump(mode="json")
    if update.emergency_contact is not None:
        payload["emergency_contact"] = update.emergency_contact.model_dump(mode="json")
    for field, value in payload.items():
        setattr(draft, field, value)
    if draft.current_step in {"lease_term", "personal_info", "emergency_contact", "review"}:
        if not draft.move_in_date:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Move-in date step is incomplete")
        availability_service = BookingAvailabilityService(session)
        valid, reason, _ = await availability_service.validate(property_obj, draft.move_in_date)
        if not valid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
    if draft.current_step in {"personal_info", "emergency_contact", "review"}:
        if not draft.lease_months:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lease term step is incomplete")
        pricing = LeasePricingService.calculate(property_obj, draft.move_in_date)
        if not any(option.months == draft.lease_months for option in pricing.options):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lease term is unavailable")
    if draft.current_step in {"emergency_contact", "review"} and not draft.personal_info:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Personal information step is incomplete")
    if draft.current_step == "review" and not draft.emergency_contact:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Emergency contact step is incomplete")
    await session.commit()
    await session.refresh(draft)
    return draft


@router.post("/confirm", response_model=BookingConfirmationRead, status_code=status.HTTP_201_CREATED)
async def confirm_booking_with_policies(
    confirmation: BookingConfirmationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingConfirmationRead:
    flow_draft = await session.scalar(select(BookingFlowDraft).where(
        BookingFlowDraft.user_id == current_user.id,
        BookingFlowDraft.property_id == confirmation.property_id,
    ))
    if (
        not flow_draft
        or flow_draft.current_step != "review"
        or not flow_draft.personal_info
        or not flow_draft.emergency_contact
        or flow_draft.move_in_date != confirmation.move_in_date
        or flow_draft.lease_months != confirmation.lease_months
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking flow steps are incomplete")

    acceptance_map = {item.key: item for item in confirmation.policy_acceptances}
    if set(acceptance_map) != set(POLICIES):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="All current policies must be accepted")
    for key, policy in POLICIES.items():
        acceptance = acceptance_map[key]
        if acceptance.version != policy.version or acceptance.content_hash != policy.content_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Policy {key} has changed; please review the latest version",
            )

    availability_service = BookingAvailabilityService(session)
    property_obj = await availability_service.get_property(confirmation.property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    valid, reason, _ = await availability_service.validate(property_obj, confirmation.move_in_date)
    if not valid:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

    pricing = LeasePricingService.calculate(property_obj, confirmation.move_in_date)
    option = next((item for item in pricing.options if item.months == confirmation.lease_months), None)
    if not option:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Lease term is unavailable")

    duplicate = await session.scalar(select(Booking).where(
        Booking.tenant_id == current_user.id,
        Booking.property_id == property_obj.id,
        Booking.status == BookingStatus.pending,
    ))
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a pending booking for this property")

    booking = Booking(
        tenant_id=current_user.id,
        property_id=property_obj.id,
        landlord_id=property_obj.landlord_id,
        status=BookingStatus.pending,
        scheduled_date=confirmation.move_in_date.isoformat(),
        deposit_amount=property_obj.deposit_amount or 0,
        service_fee=option.prices.service_fee.local.minor_units // (10 ** option.prices.service_fee.local.minor_unit_exponent),
        deposit_status="unpaid",
        lease_months=confirmation.lease_months,
        total_rent=option.prices.rent_total.local.minor_units // (10 ** option.prices.rent_total.local.minor_unit_exponent),
        application_data={
            "pricing_snapshot": pricing.model_dump(mode="json"),
            "personal_info": flow_draft.personal_info,
            "emergency_contact": flow_draft.emergency_contact,
        },
    )
    session.add(booking)
    await session.flush()

    ip_address = request.client.host if request.client else "unknown"
    for policy in POLICIES.values():
        session.add(PolicyConsent(
            booking_id=booking.id,
            user_id=current_user.id,
            policy_key=policy.key,
            policy_version=policy.version,
            content_hash=policy.content_hash,
            ip_address=ip_address,
        ))
    await session.delete(flow_draft)
    await session.commit()
    return BookingConfirmationRead(booking_id=booking.id, consent_count=len(POLICIES))


@router.post("/emergency-contact/validate", response_model=BookingEmergencyContactValidationRead)
async def validate_booking_emergency_contact(
    _contact: BookingEmergencyContactValidation,
    _current_user: User = Depends(require_tenant),
) -> BookingEmergencyContactValidationRead:
    return BookingEmergencyContactValidationRead(valid=True)


@router.post("/personal-info/validate", response_model=BookingPersonalInfoValidationRead)
async def validate_booking_personal_info(
    _personal_info: BookingPersonalInfoValidation,
    _current_user: User = Depends(require_tenant),
) -> BookingPersonalInfoValidationRead:
    return BookingPersonalInfoValidationRead(valid=True)


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_in: BookingCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> BookingRead:
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
    if update_in.status not in {BookingStatus.approved, BookingStatus.rejected}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be approved or rejected",
        )

    booking_service = BookingService(session)
    booking = await booking_service.get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != booking.landlord_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the landlord can update this booking")

    updated = await booking_service.update_status(booking_id, update_in.status)
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
