from pydantic import BaseModel, ConfigDict, Field


class SystemAlertCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    severity: str = Field(..., pattern="^(high|medium|low)$")
    title: str = Field(..., min_length=1, max_length=120)
    summary: str = Field(..., min_length=1, max_length=300)
    detail: str | None = None
    source: str = Field(..., min_length=1, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)
    action_type: str | None = Field(default=None, max_length=60)
    action_label: str | None = Field(default=None, max_length=60)
    action_resource_id: str | None = Field(default=None, max_length=120)
    extra: dict | None = None


class SystemAlertRead(BaseModel):
    id: int
    category: str
    severity: str
    title: str
    summary: str
    detail: str | None
    source: str
    source_id: str | None
    status: str
    action_type: str | None
    action_label: str | None
    action_resource_id: str | None
    created_at: str
    updated_at: str
    resolved_at: str | None = None

    model_config = ConfigDict(from_attributes=True)
