from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContractCreate(BaseModel):
    booking_id: int


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    booking_id: int
    tenant_id: int
    property_id: int
    template_name: str
    content: str
    status: str
    signed_at: datetime | None = None
    file_path: str | None = None
    created_at: datetime
    updated_at: datetime