"""第三方嵌入式签署接口的请求与响应定义。"""

from pydantic import BaseModel, Field


class EmbeddedSigningStart(BaseModel):
    """租客确认电子签署后创建或继续嵌入式签署会话。"""

    electronic_signature_consent: bool
    consent_text_version: str = Field(min_length=1, max_length=32)


class EmbeddedSigningSession(BaseModel):
    """供前端嵌入 Dropbox Sign 的一次性会话信息。"""

    signature_request_id: str
    sign_url: str
    expires_at: int | None = None
    # Client ID 是嵌入式 SDK 所需的公开应用标识，不是 API Key。
    client_id: str
    test_mode: bool


class TemplateBindingCreate(BaseModel):
    """管理员配置 Dropbox Sign 模板与系统字段的映射。"""

    institute_id: int | None = None
    provider_template_id: str = Field(min_length=1, max_length=128)
    signer_role: str = Field(min_length=1, max_length=100)
    field_mapping: dict[str, str] = Field(default_factory=dict)
    is_default: bool = False


class TemplateBindingRead(TemplateBindingCreate):
    id: str
    provider: str
    is_active: bool
    model_config = {"from_attributes": True}


class TemplateBindingUpdate(BaseModel):
    """绑定只允许更新同一公寓的模板标识、签署角色和字段映射。"""

    provider_template_id: str | None = Field(default=None, min_length=1, max_length=128)
    signer_role: str | None = Field(default=None, min_length=1, max_length=100)
    field_mapping: dict[str, str] | None = None
    is_active: bool | None = None
