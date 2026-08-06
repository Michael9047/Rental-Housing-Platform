"""统一解析合同执行渠道，避免租客页面同时走本地模拟与第三方签署。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.booking import Booking
from app.models.contract import Contract
from app.models.external_signature import ExternalSignatureTemplateBinding


class ContractExecutionService:
    """根据订单所属公寓的有效绑定，给出唯一的合同签署渠道。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, contract: Contract) -> dict:
        booking = await self.session.get(Booking, contract.booking_id)
        institute_id = booking.institute_id if booking else None
        binding = None
        if institute_id is not None:
            binding = await self.session.scalar(
                select(ExternalSignatureTemplateBinding).where(
                    ExternalSignatureTemplateBinding.institute_id == institute_id,
                    ExternalSignatureTemplateBinding.provider == "dropbox_sign",
                    ExternalSignatureTemplateBinding.is_active.is_(True),
                ).order_by(ExternalSignatureTemplateBinding.updated_at.desc())
            )
        if binding is None:
            binding = await self.session.scalar(
                select(ExternalSignatureTemplateBinding).where(
                    ExternalSignatureTemplateBinding.institute_id.is_(None),
                    ExternalSignatureTemplateBinding.provider == "dropbox_sign",
                    ExternalSignatureTemplateBinding.is_default.is_(True),
                    ExternalSignatureTemplateBinding.is_active.is_(True),
                )
            )
        if binding is None:
            return {"mode": "mock_sign", "available": True, "label": "本地实验模拟签署", "reason": "该公寓尚未绑定 Dropbox Sign 模板"}
        settings = get_settings()
        available = bool(settings.dropbox_sign_api_key and settings.dropbox_sign_client_id)
        if not available:
            return {
                "mode": "mock_sign", "available": True, "label": "本地实验模拟签署",
                "reason": "Dropbox Sign 模板已保留，但服务端尚未配置完成；当前使用系统默认实验合同",
                "pending_provider": "dropbox_sign",
            }
        return {
            "mode": "dropbox_sign",
            "available": available,
            "label": "Dropbox Sign 嵌入式签署",
            "reason": None if available else "Dropbox Sign 服务端尚未完成 API Key 或 Client ID 配置",
            "template_id": binding.provider_template_id,
            "signer_role": binding.signer_role,
        }
