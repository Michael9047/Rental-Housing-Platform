from fastapi import APIRouter, HTTPException, status

from app.schemas.geocoding import GeocodeRequest, GeocodeResponse
from app.services.geocoding_service import geocode_with_fallback

router = APIRouter(prefix="/geo", tags=["geo"])


@router.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(payload: GeocodeRequest) -> GeocodeResponse:
    try:
        result = await geocode_with_fallback(
            payload.address,
            payload.city,
            payload.country,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return GeocodeResponse(**result.__dict__)
