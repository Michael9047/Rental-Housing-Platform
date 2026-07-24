from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PropertyImageCreate(BaseModel):
    pass


class PropertyImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    filename: str
    original_name: str
    mime_type: str
    file_size: int
    sort_order: int
    is_primary: bool
    created_at: datetime
