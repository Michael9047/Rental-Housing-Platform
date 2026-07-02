import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.contract import Contract
from app.models.property import Property
from app.models.user import User

logger = logging.getLogger(__name__)


class ContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _format_contract_date(date_text: str | None) -> str:
        if not date_text:
            return "____年____月____日"
        parts = date_text.split("-")
        if len(parts) == 3:
            return f"{parts[0]}年{parts[1]}月{parts[2]}日"
        return date_text

    @staticmethod
    def _has_confirmed_contract_info(booking: Booking) -> bool:
        required_fields = (
            booking.contract_real_name,
            booking.contract_id_card_no,
            booking.contract_phone,
            booking.lease_start_date,
            booking.lease_end_date,
        )
        return booking.contract_info_status == "confirmed" and all(required_fields)

    async def generate_contract(self, booking: Booking) -> Contract:
        """Generate a Chinese rental contract template filled with booking data."""
        existing = await self.session.execute(
            select(Contract).where(Contract.booking_id == booking.id)
        )
        existing_contract = existing.scalars().first()
        if existing_contract:
            return existing_contract

        if not self._has_confirmed_contract_info(booking):
            raise ValueError("Contract info must be submitted by tenant and confirmed by landlord before generating")

        tenant = await self.session.get(User, booking.tenant_id)
        landlord = await self.session.get(User, booking.landlord_id)
        property_obj = await self.session.get(Property, booking.property_id)

        landlord_name = landlord.username if landlord else "房东"
        tenant_name = booking.contract_real_name or (tenant.username if tenant else "租客")
        tenant_phone = booking.contract_phone or (tenant.phone if tenant else "")
        tenant_id_card_no = booking.contract_id_card_no or "未填写"
        lease_start_date = self._format_contract_date(booking.lease_start_date)
        lease_end_date = self._format_contract_date(booking.lease_end_date)
        extra_terms = booking.contract_extra_terms or "无"
        deposit = booking.deposit_amount or (property_obj.deposit_amount if property_obj else 1000)
        property_address = property_obj.address if property_obj else "未指定地址"
        property_title = property_obj.title if property_obj else "未指定物业"
        price = float(property_obj.price_monthly) if property_obj else 0

        content = f"""租赁合同

甲方（出租方）：{landlord_name}
房屋名称：{property_title}
房屋地址：{property_address}

乙方（承租方）：{tenant_name}
身份证号：{tenant_id_card_no}
联系电话：{tenant_phone}

第一条 租赁房屋
甲方将位于{property_address}的房屋出租给乙方使用。

第二条 租赁期限
租赁期限自{lease_start_date}起至{lease_end_date}止。

第三条 租金
月租金为人民币{price:.2f}元，乙方应于每月____日前支付。

第四条 押金
乙方应于签订本合同时向甲方支付押金人民币{deposit}元。

第五条 其他约定
1. 乙方应合理使用房屋，不得擅自改变房屋结构。
2. 乙方应按时缴纳水、电、煤气、物业管理等相关费用。
3. 租赁期满，乙方应将房屋完好交还甲方。
4. 合同期内如一方违约，应赔偿对方相应损失。

第六条 补充约定
{extra_terms}

第七条 争议解决
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
        return contract

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
        return contract
