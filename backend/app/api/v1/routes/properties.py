from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.models.user import User
from app.schemas.property import PropertyCreate, PropertyRead, PropertySearchResult, PropertyUpdate
from app.schemas.property_image import PropertyImageRead
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


@router.get("/search", response_model=list[PropertySearchResult])
async def search_properties(
    q: str | None = Query(default=None, description="Natural language search query"),
    district: str | None = Query(default=None),
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    bedrooms: int | None = Query(default=None, ge=0),
    property_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[PropertySearchResult]:
    results = await PropertyService(session).search(
        query=q,
        district=district,
        price_min=price_min,
        price_max=price_max,
        bedrooms=bedrooms,
        property_type=property_type,
        limit=limit,
    )
    return [
        PropertySearchResult(
            id=prop.id,
            landlord_id=prop.landlord_id,
            title=prop.title,
            description=prop.description,
            address=prop.address,
            district=prop.district,
            price_monthly=prop.price_monthly,
            area_sqm=prop.area_sqm,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            property_type=prop.property_type,
            status=prop.status,
            latitude=prop.latitude,
            longitude=prop.longitude,
            created_at=prop.created_at,
            updated_at=prop.updated_at,
            images=[
                PropertyImageRead(
                    id=img.id,
                    property_id=img.property_id,
                    filename=img.filename,
                    original_name=img.original_name,
                    mime_type=img.mime_type,
                    file_size=img.file_size,
                    sort_order=img.sort_order,
                    is_primary=img.is_primary,
                    created_at=img.created_at,
                )
                for img in (prop.images or [])
            ],
            institute_id=prop.institute_id,
            institute_name=getattr(prop, 'institute_name', None),
            similarity=sim,
        )
        for prop, sim in results
    ]


@router.get("", response_model=list[PropertyRead])
async def list_properties(
    session: AsyncSession = Depends(get_db_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    district: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    landlord_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None, description="搜索房号/标题/地址"),
    property_type: str | None = Query(default=None, description="户型筛选"),
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
) -> list[PropertyRead]:
    return await PropertyService(session).list(
        skip=skip,
        limit=limit,
        district=district,
        status=status_filter,
        landlord_id=landlord_id,
        keyword=keyword,
        property_type=property_type,
        price_min=price_min,
        price_max=price_max,
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