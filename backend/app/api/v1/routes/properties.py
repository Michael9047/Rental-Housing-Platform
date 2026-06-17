from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.schemas.property import PropertyCreate, PropertyRead, PropertyUpdate
from app.services.property_service import PropertyService
from app.services.user_service import UserService

router = APIRouter()


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_in: PropertyCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> PropertyRead:
    landlord = await UserService(session).get(property_in.landlord_id)
    if not landlord:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="landlord_id does not reference an existing user",
        )
    if current_user.role.value != "admin" and property_in.landlord_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlords can only create properties for themselves",
        )
    return await PropertyService(session).create(property_in)


@router.get("", response_model=list[PropertyRead])
async def list_properties(
    session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    district: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[PropertyRead]:
    return await PropertyService(session).list(
        skip=skip,
        limit=limit,
        district=district,
        status=status_filter,
    )


@router.get("/{property_id}", response_model=PropertyRead)
async def get_property(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> PropertyRead:
    property_obj = await PropertyService(session).get(property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return property_obj


@router.patch("/{property_id}", response_model=PropertyRead)
async def update_property(
    property_id: int,
    property_in: PropertyUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> PropertyRead:
    property_service = PropertyService(session)
    existing_property = await property_service.get(property_id)
    if not existing_property:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role.value != "admin" and existing_property.landlord_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlords can only update their own properties",
        )

    property_obj = await property_service.update(property_id, property_in)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return property_obj


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> None:
    property_service = PropertyService(session)
    existing_property = await property_service.get(property_id)
    if not existing_property:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role.value != "admin" and existing_property.landlord_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlords can only delete their own properties",
        )

    deleted = await property_service.delete(property_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
