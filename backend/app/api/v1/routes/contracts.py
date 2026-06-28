from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_tenant
from app.models.user import User, UserRole
from app.schemas.contract import ContractResponse
from app.services.booking_service import BookingService
from app.services.contract_service import ContractService

router = APIRouter()


async def ensure_contract_access(
    contract_id: str,
    session: AsyncSession,
    current_user: User,
) -> ContractResponse:
    contract = await ContractService(session).get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    if current_user.role == UserRole.admin or current_user.id == contract.tenant_id:
        return contract

    booking = await BookingService(session).get(contract.booking_id)
    if not booking or current_user.id != booking.landlord_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return contract


@router.post("/{booking_id}/generate", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def generate_contract(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    booking = await BookingService(session).get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id not in {booking.tenant_id, booking.landlord_id} and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    contract_service = ContractService(session)
    try:
        contract = await contract_service.generate_contract(booking)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return contract


@router.get("/by-booking/{booking_id}", response_model=ContractResponse)
async def get_contract_by_booking(
    booking_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    booking = await BookingService(session).get(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id not in {booking.tenant_id, booking.landlord_id} and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    contract = await ContractService(session).list_by_booking(booking_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    return contract


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContractResponse:
    return await ensure_contract_access(contract_id, session, current_user)


@router.post("/{contract_id}/sign", response_model=ContractResponse)
async def sign_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_tenant),
) -> ContractResponse:
    contract = await ensure_contract_access(contract_id, session, current_user)

    if current_user.id != contract.tenant_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the tenant can sign")

    if contract.status == "signed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contract already signed")

    updated = await ContractService(session).sign_contract(contract_id)
    return updated


@router.get("/{contract_id}/download", response_class=PlainTextResponse)
async def download_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PlainTextResponse:
    contract = await ensure_contract_access(contract_id, session, current_user)

    return PlainTextResponse(content=contract.content, media_type="text/plain; charset=utf-8")
