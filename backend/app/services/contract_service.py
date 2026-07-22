"""电子合同生成、查询与签署服务。"""

import calendar
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.contract import Contract
from app.models.notification import NotificationType
from app.models.property import Property
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

PROPERTY_TYPE_LABELS = {
    "apartment": "公寓",
    "house": "独立住宅",
    "studio": "单间公寓",
    "shared": "合租房",
}
COUNTRY_LABELS = {
    "CN": "中国大陆",
    "HK": "中国香港",
    "MO": "中国澳门",
    "TW": "中国台湾",
    "SG": "新加坡",
    "GB": "英国",
    "US": "美国",
    "AU": "澳大利亚",
    "DE": "德国",
    "FR": "法国",
    "NL": "荷兰",
    "CA": "加拿大",
    "JP": "日本",
    "KR": "韩国",
    "OT": "其他国家或地区",
}
RENT_TYPE_LABELS = {
    "monthly": "按月支付",
    "quarterly": "按季度支付",
    "yearly": "按年支付",
}
DEPOSIT_TYPE_LABELS = {
    "one_month": "押一付一",
    "one_three": "押一付三",
    "two_month": "押二付一",
    "three_month": "押三付一",
    "half_month": "押半付一",
    "free": "免押金",
    "custom": "自定义押付方式",
}


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _as_number(value: Any) -> float | int | None:
    if value is None:
        return None
    number = Decimal(str(value))
    return int(number) if number == number.to_integral_value() else float(number)


def _format_money(value: Any) -> str:
    if value is None:
        return "待双方确认"
    return f"人民币 {Decimal(str(value)):,.2f} 元"


def _parse_contract_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _lease_end_date(start_date: date | None, lease_months: int | None) -> date | None:
    if not start_date or not lease_months:
        return None
    month_index = start_date.month - 1 + lease_months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day) - timedelta(days=1)


def _date_text(value: date | None) -> str:
    return value.strftime("%Y年%m月%d日") if value else "待双方确认"


def _build_property_snapshot(property_obj: Property | None, booking: Booking) -> dict:
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    if not property_obj:
        return {
            "id": booking.property_id,
            "title": "房源信息待补充",
            "captured_at": captured_at,
            "source": "platform_property_database",
        }

    return {
        "id": property_obj.id,
        "title": property_obj.title,
        "description": property_obj.description,
        "address": property_obj.address,
        "district": property_obj.district,
        "country": _enum_value(property_obj.country),
        "property_type": _enum_value(property_obj.property_type),
        "price_monthly": _as_number(property_obj.price_monthly),
        "area_sqm": _as_number(property_obj.area_sqm),
        "bedrooms": property_obj.bedrooms,
        "bathrooms": property_obj.bathrooms,
        "floor": property_obj.floor,
        "room_number": property_obj.room_number,
        "amenities": list(property_obj.amenities or []),
        "available_from": property_obj.available_from.isoformat()
        if property_obj.available_from
        else None,
        "min_lease_months": property_obj.min_lease_months,
        "max_lease_months": property_obj.max_lease_months,
        "rent_type": _enum_value(property_obj.rent_type),
        "deposit_amount": property_obj.deposit_amount,
        "deposit_type": _enum_value(property_obj.deposit_type),
        "service_fee_rate": property_obj.service_fee_rate,
        "property_updated_at": property_obj.updated_at.isoformat()
        if property_obj.updated_at
        else None,
        "captured_at": captured_at,
        "source": "platform_property_database",
    }


class ContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_contract(self, booking: Booking) -> Contract:
        """生成包含房源快照与预约条款的中文租赁合同。"""
        existing = await self.session.execute(
            select(Contract).where(Contract.booking_id == booking.id)
        )
        if existing.scalars().first():
            raise ValueError("Contract already exists for this booking")

        tenant = await self.session.get(User, booking.tenant_id)
        landlord = await self.session.get(User, booking.landlord_id)
        property_obj = await self.session.get(Property, booking.property_id)

        tenant_name = tenant.username if tenant else "租客"
        landlord_name = landlord.username if landlord else "出租方"
        deposit = (
            booking.deposit_amount
            if booking.deposit_amount is not None
            else property_obj.deposit_amount if property_obj else None
        )
        service_fee = booking.service_fee
        property_address = property_obj.address if property_obj else "未指定地址"
        property_title = property_obj.title if property_obj else "未指定物业"
        price = property_obj.price_monthly if property_obj else None
        lease_months = booking.lease_months
        total_rent = booking.total_rent
        if total_rent is None and price is not None and lease_months:
            total_rent = int(Decimal(str(price)) * lease_months)

        start_date = _parse_contract_date(booking.scheduled_date)
        end_date = _lease_end_date(start_date, lease_months)
        snapshot = _build_property_snapshot(property_obj, booking)
        property_type = PROPERTY_TYPE_LABELS.get(
            str(snapshot.get("property_type") or ""), "未记录"
        )
        country = COUNTRY_LABELS.get(
            str(snapshot.get("country") or ""),
            str(snapshot.get("country") or "未记录"),
        )
        rent_type = RENT_TYPE_LABELS.get(
            str(snapshot.get("rent_type") or ""), "待双方确认"
        )
        deposit_type = DEPOSIT_TYPE_LABELS.get(
            str(snapshot.get("deposit_type") or ""), "按合同约定"
        )
        area_text = (
            f"{snapshot['area_sqm']} 平方米"
            if snapshot.get("area_sqm") is not None
            else "未记录"
        )
        layout_text = (
            f"{snapshot.get('bedrooms', 0)} 室 "
            f"{snapshot.get('bathrooms', 0)} 卫"
        )
        floor_text = (
            f"{snapshot['floor']} 层"
            if snapshot.get("floor") is not None
            else "未记录"
        )
        room_text = str(snapshot.get("room_number") or "未记录")
        amenities_text = "、".join(snapshot.get("amenities") or []) or "未记录"
        description_text = str(snapshot.get("description") or "未记录")
        lease_text = f"{lease_months} 个月" if lease_months else "待双方确认"
        lease_range_text = (
            f"{snapshot.get('min_lease_months')} 至 {snapshot.get('max_lease_months')} 个月"
            if snapshot.get("max_lease_months")
            else f"不少于 {snapshot.get('min_lease_months')} 个月"
            if snapshot.get("min_lease_months")
            else "未记录"
        )
        contract_id = str(uuid.uuid4())
        contract_number = f"HT{contract_id.replace('-', '')[:12].upper()}"
        generated_at = datetime.now().astimezone().strftime("%Y年%m月%d日 %H:%M")

        content = f"""房屋租赁合同（电子版）

合同编号：{contract_number}
预约编号：#{booking.id}
合同生成时间：{generated_at}

甲方（出租方）：{landlord_name}（用户编号 #{booking.landlord_id}）
乙方（承租方）：{tenant_name}（用户编号 #{booking.tenant_id}）

第一条 房屋基本信息
1. 房源名称：{property_title}
2. 房源编号：#{booking.property_id}
3. 房屋坐落：{property_address}
4. 所在区域：{country} / {snapshot.get('district') or '未记录'}
5. 房屋类型：{property_type}；户型：{layout_text}；面积：{area_text}
6. 楼层与房号：{floor_text} / {room_text}
7. 配套设施：{amenities_text}
8. 房源说明：{description_text}
9. 房源可租期：{lease_range_text}

第二条 租赁期限
1. 约定起租日：{_date_text(start_date)}
2. 约定到期日：{_date_text(end_date)}
3. 约定租期：{lease_text}
4. 如起租日或租期尚未确认，双方须在签署前补充确认，确认内容构成本合同的一部分。

第三条 租金、押金及相关费用
1. 月租金：{_format_money(price)}。
2. 租期租金合计：{_format_money(total_rent)}。
3. 租金支付周期：{rent_type}，具体支付日以双方最终确认的账单为准。
4. 押金：{_format_money(deposit)}；押付方式：{deposit_type}。
5. 平台服务费：{_format_money(service_fee)}。
6. 水、电、燃气、网络、物业管理等费用的承担方式，由双方在交房清单或补充协议中确认。

第四条 房屋交付与设施确认
1. 甲方应按约定时间交付房屋，并保证房屋具备正常居住条件。
2. 双方交付时应共同核验房屋、家具家电、钥匙及表计读数，形成交接清单。
3. 本合同记录的设施来自合同生成时的平台房源快照；实际交付差异应写入交接清单并由双方确认。

第五条 房屋使用与维修
1. 乙方应合理使用房屋及附属设施，不得擅自改变主体结构或从事违法活动。
2. 因正常使用产生的维修责任、因不当使用造成的损坏责任，按法律规定及双方补充约定承担。
3. 未经甲方书面同意，乙方不得擅自转租或改变房屋用途。

第六条 退租、违约与押金返还
1. 合同期满或提前解除时，双方应办理房屋验收、费用结清和钥匙交还。
2. 押金在扣除依法或依约应由乙方承担的费用后返还，具体时限以双方最终签署条款为准。
3. 任一方违约，应按照双方最终确认的违约条款及适用法律承担责任。

第七条 争议解决与合同效力
1. 本合同为电子合同，与依法成立的纸质合同具有同等效力。
2. 因履行本合同发生争议，双方应先协商解决；协商不成的，按房屋所在地适用法律及管辖规则处理。
3. 未尽事宜由双方另行签订补充协议，补充协议与本合同具有同等效力。

甲方签字：____________    日期：____________
乙方签字：____________    日期：____________
"""
        contract = Contract(
            id=contract_id,
            booking_id=booking.id,
            tenant_id=booking.tenant_id,
            property_id=booking.property_id,
            template_name="standard_lease_v2",
            content=content,
            property_snapshot=snapshot,
            status="draft",
        )
        self.session.add(contract)
        await self.session.commit()
        await self.session.refresh(contract)

        # 通知租客和房东
        notification_service = NotificationService(self.session)
        await notification_service.create_notification(
            user_id=contract.tenant_id,
            type=NotificationType.contract_generated,
            title="合同已生成",
            content=f"您对 {property_title} 的租赁合同已生成，请前往签署",
            channels=["email"],
        )
        if booking.landlord_id:
            await notification_service.create_notification(
                user_id=booking.landlord_id,
                type=NotificationType.contract_generated,
                title="合同已生成",
                content=f"预约 #{booking.id} 的租赁合同已生成，等待租客签署",
                channels=["email"],
            )

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

        # 通知租客和房东
        booking = await self.session.get(Booking, contract.booking_id)
        notification_service = NotificationService(self.session)
        await notification_service.create_notification(
            user_id=contract.tenant_id,
            type=NotificationType.contract_signed,
            title="合同已签署",
            content=f"您已成功签署预约 #{contract.booking_id} 的租赁合同",
            channels=["email"],
        )
        if booking and booking.landlord_id:
            await notification_service.create_notification(
                user_id=booking.landlord_id,
                type=NotificationType.contract_signed,
                title="合同已被签署",
                content=f"租客已签署预约 #{contract.booking_id} 的租赁合同",
                channels=["email"],
            )

        return contract
