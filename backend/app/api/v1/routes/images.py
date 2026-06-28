import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_landlord
from app.core.config import get_settings
from app.models.user import User
from app.schemas.property_image import PropertyImageRead
from app.services.image_service import ImageService
from app.services.property_service import PropertyService

router = APIRouter()


def get_upload_dir() -> Path:
    settings = get_settings()
    upload_dir = Path(settings.upload_dir).resolve()
    if not upload_dir.exists():
        upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


@router.post(
    "/{property_id}/images",
    response_model=list[PropertyImageRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_images(
    property_id: int,
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> list[PropertyImageRead]:
    settings = get_settings()

    # Verify property exists and belongs to user
    property_service = PropertyService(session)
    property_obj = await property_service.get(property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role.value != "admin" and property_obj.landlord_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only upload images to your own properties",
        )

    image_service = ImageService(session)

    # Check image count limit
    current_count = await image_service.count_by_property(property_id)
    if current_count + len(files) > settings.max_images_per_property:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.max_images_per_property} images per property",
        )

    # Validate file types
    for file in files:
        if file.content_type not in settings.allowed_image_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file.content_type}",
            )
        if file.size and file.size > settings.max_upload_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large: {file.filename}",
            )

    images = []
    for idx, file in enumerate(files):
        image = await image_service.save_upload(
            file, property_id, sort_order=current_count + idx
        )
        images.append(image)

    return images


@router.delete(
    "/{property_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_image(
    property_id: int,
    image_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> None:
    property_service = PropertyService(session)
    property_obj = await property_service.get(property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role.value != "admin" and property_obj.landlord_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete images from your own properties",
        )

    image_service = ImageService(session)
    deleted = await image_service.delete_image(image_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")


@router.patch(
    "/{property_id}/images/{image_id}/primary",
    response_model=PropertyImageRead,
)
async def set_primary_image(
    property_id: int,
    image_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_landlord),
) -> PropertyImageRead:
    property_service = PropertyService(session)
    property_obj = await property_service.get(property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role.value != "admin" and property_obj.landlord_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only manage images for your own properties",
        )

    image_service = ImageService(session)
    image = await image_service.set_primary(image_id)
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image


@router.get(
    "/{property_id}/images",
    response_model=list[PropertyImageRead],
)
async def list_images(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> list[PropertyImageRead]:
    property_service = PropertyService(session)
    property_obj = await property_service.get(property_id)
    if not property_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    image_service = ImageService(session)
    return await image_service.get_by_property(property_id)
