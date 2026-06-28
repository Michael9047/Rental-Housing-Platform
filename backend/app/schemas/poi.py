from datetime import datetime

from pydantic import BaseModel, ConfigDict


class POIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: int
    content: str
    poi_data: dict | None = None
    generated_at: datetime
    reviewed: bool
    created_at: datetime
    updated_at: datetime