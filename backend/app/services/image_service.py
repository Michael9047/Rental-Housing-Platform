import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.property_image import PropertyImage


class ImageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    @property
    def upload_dir(self) -> Path:
        return Path(self.settings.upload_dir).resolve()

    async def count_by_property(self, property_id: int) -> int:
        stmt = select(PropertyImage).where(PropertyImage.property_id == property_id)
        result = await self.session.scalars(stmt)
        return len(list(result))

    async def save_upload(
        self, file: UploadFile, property_id: int, sort_order: int
    ) -> PropertyImage:
        ext = os.path.splitext(file.filename or ".jpg")[1] or ".jpg"
        safe_filename = f"{uuid.uuid4().hex}{ext}"

        file_path = self.upload_dir / safe_filename
        content = await file.read()
        file_path.write_bytes(content)

        # Determine if this should be the primary image
        count = await self.count_by_property(property_id)

        image = PropertyImage(
            property_id=property_id,
            filename=safe_filename,
            original_name=file.filename or "untitled",
            mime_type=file.content_type or "image/jpeg",
            file_size=len(content),
            sort_order=sort_order,
            is_primary=(count == 0),
        )
        self.session.add(image)
        await self.session.commit()
        await self.session.refresh(image)
        return image

    async def delete_image(self, image_id: int) -> bool:
        image = await self.session.get(PropertyImage, image_id)
        if not image:
            return False

        # Delete file from disk
        file_path = self.upload_dir / image.filename
        if file_path.exists():
            file_path.unlink()

        await self.session.delete(image)
        await self.session.commit()
        return True

    async def set_primary(self, image_id: int) -> PropertyImage | None:
        image = await self.session.get(PropertyImage, image_id)
        if not image:
            return None

        # Unset all other primary images for this property
        stmt = (
            update(PropertyImage)
            .where(PropertyImage.property_id == image.property_id)
            .values(is_primary=False)
        )
        await self.session.execute(stmt)

        # Set this one as primary
        image.is_primary = True
        await self.session.commit()
        await self.session.refresh(image)
        return image

    async def get_by_property(self, property_id: int) -> list[PropertyImage]:
        stmt = (
            select(PropertyImage)
            .where(PropertyImage.property_id == property_id)
            .order_by(PropertyImage.sort_order, PropertyImage.id)
        )
        result = await self.session.scalars(stmt)
        return list(result)
