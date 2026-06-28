from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.poi import POIResponse
from app.services.poi_service import POIService

router = APIRouter()


@router.post("/{property_id}/generate", response_model=POIResponse, status_code=status.HTTP_201_CREATED)
async def generate_poi(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse:
    poi_service = POIService(session)
    poi = await poi_service.get_or_generate_poi(property_id)
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return poi


@router.get("/{property_id}", response_model=POIResponse)
async def get_poi(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse:
    poi_service = POIService(session)
    poi = await poi_service.get_or_generate_poi(property_id)
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI not found for this property")
    return poi