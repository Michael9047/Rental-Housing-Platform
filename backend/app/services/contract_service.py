import base64
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.contract import Contract
from app.models.notification import NotificationType
from app.models.property import Property
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_contract(self, booking: Booking) -> Contract:
        """Generate a Chinese rental contract template filled with booking data."""
        existing = await self.session.execute(
            select(Contract).where(Contract.booking_id == booking.id)
        )
        if existing.scalars().first():
            raise ValueError("Contract already exists for this booking")

        tenant = await self.session.get(User, booking.tenant_id)
        property_obj = await self.session.get(Property, booking.property_id)

        tenant_name = tenant.username if tenant else "租客"
        deposit = booking.deposit_amount or (property_obj.deposit_amount if property_obj else 1000)
        property_address = property_obj.address if property_obj else "未指定地址"
        property_title = property_obj.title if property_obj else "未指定物业"
        price = float(property_obj.price_monthly) if property_obj else 0

        content = f"""租赁合同

甲方（出租方）：{property_title}
地址：{property_address}

乙方（承租方）：{tenant_name}

第一条 租赁房屋
甲方将位于{property_address}的房屋出租给乙方使用。

第二条 租赁期限
租赁期限自____年____月____日起至____年____月____日止。

第三条 租金
月租金为人民币{price:.2f}元，乙方应于每月____日前支付。

第四条 押金
乙方应于签订本合同时向甲方支付押金人民币{deposit}元。

第五条 其他约定
1. 乙方应合理使用房屋，不得擅自改变房屋结构。
2. 乙方应按时缴纳水、电、煤气、物业管理等相关费用。
3. 租赁期满，乙方应将房屋完好交还甲方。
4. 合同期内如一方违约，应赔偿对方相应损失。

第六条 争议解决
本合同在履行过程中发生争议，由双方协商解决；协商不成的，依法向房屋所在地人民法院起诉。

甲方签字：____________    日期：____________
乙方签字：____________    日期：____________
"""
        contract = Contract(
            booking_id=booking.id,
            tenant_id=booking.tenant_id,
            property_id=booking.property_id,
            template_name="standard_lease",
            content=content,
            status="draft",
        )
        self.session.add(contract)
        await self.session.commit()
        await self.session.refresh(contract)

        # 生成合同 PDF（用于邮件附件）
        pdf_attachments = await self._build_pdf_attachments(
            contract, property_title,
        )

        # 通知租客和房东（带 PDF 附件）
        notification_service = NotificationService(self.session)
        await notification_service.create_notification(
            user_id=contract.tenant_id,
            type=NotificationType.contract_generated,
            title="合同已生成",
            content=f"您对 {property_title} 的租赁合同已生成，请前往签署",
            channels=["email"],
            email_attachments=pdf_attachments,
        )
        if booking.landlord_id:
            await notification_service.create_notification(
                user_id=booking.landlord_id,
                type=NotificationType.contract_generated,
                title="合同已生成",
                content=f"预约 #{booking.id} 的租赁合同已生成，等待租客签署",
                channels=["email"],
                email_attachments=pdf_attachments,
            )

        return contract

    # ── PDF 附件辅助方法 ──────────────────────────────────────

    async def _build_pdf_attachments(
        self,
        contract: Contract,
        property_title: str,
        suffix: str = "",
    ) -> Optional[list[dict]]:
        """生成合同 PDF 并转为 Base64 编码的附件列表。

        失败时返回 None（不阻塞通知发送）。
        """
        try:
            from app.services.contract_pdf_service import ContractPdfService

            pdf_service = ContractPdfService()
            pdf_bytes = await pdf_service.generate(contract)

            # 构建文件名
            label = f"{suffix}-" if suffix else ""
            filename = f"租赁合同-{label}{property_title}-{contract.id[:8]}.pdf"

            return [{
                "filename": filename,
                "content_b64": base64.b64encode(pdf_bytes).decode("ascii"),
            }]
        except ImportError:
            logger.warning(
                "weasyprint 未安装，跳过合同 PDF 生成 contract_id=%s",
                contract.id,
            )
            return None
        except Exception as exc:
            logger.exception(
                "合同 PDF 生成失败，跳过附件 contract_id=%s",
                contract.id,
            )
            return None

    async def get_contract(self, contract_id: str) -> Contract | None:
        return await self.session.get(Contract, contract_id)

    async def list_by_booking(self, booking_id: int) -> Contract | None:
        stmt = select(Contract).where(Contract.booking_id == booking_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def sign_contract(self, contract_id: str) -> Contract | None:
        contract = await self.session.get(Contract, contract_id)
        if not contract:
            return None
        contract.status = "signed"
        contract.signed_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(contract)

        # 获取房源名称用于附件文件名和通知
        booking = await self.session.get(Booking, contract.booking_id)
        property_obj = await self.session.get(Property, contract.property_id) if contract.property_id else None
        property_title = property_obj.title if property_obj else "未指定物业"

        # 生成签署完成的合同 PDF（用于邮件附件）
        pdf_attachments = await self._build_pdf_attachments(
            contract, property_title, suffix="已签署",
        )

        # 通知租客和房东（带签署版 PDF 附件）
        notification_service = NotificationService(self.session)
        await notification_service.create_notification(
            user_id=contract.tenant_id,
            type=NotificationType.contract_signed,
            title="合同已签署",
            content=f"您已成功签署预约 #{contract.booking_id} 的租赁合同",
            channels=["email"],
            email_attachments=pdf_attachments,
        )
        if booking and booking.landlord_id:
            await notification_service.create_notification(
                user_id=booking.landlord_id,
                type=NotificationType.contract_signed,
                title="合同已被签署",
                content=f"租客已签署预约 #{contract.booking_id} 的租赁合同",
                channels=["email"],
                email_attachments=pdf_attachments,
            )

        return contract
