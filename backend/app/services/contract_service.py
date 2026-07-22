"""从订单不可变快照生成中英双语房屋预订及租赁协议。"""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.contract import Contract
from app.models.policy_consent import PolicyConsent
from app.models.property import Property, PropertyType
from app.models.user import User
from app.services.lease_pricing_service import LeasePricingService


TEMPLATE_VERSION = "2026.1"
DEVELOPMENT_NOTICE = "业务开发模板，待房源所在地法务审核"
PLATFORM_NAME = "Rental Housing Platform / 租房平台"
PLATFORM_ROLE = "预订信息与交易流程中介平台 / booking intermediary and process facilitator"

PROPERTY_TYPE_LABELS = {
    PropertyType.apartment: "公寓 / Apartment",
    PropertyType.house: "住宅 / House",
    PropertyType.studio: "单间公寓 / Studio",
    PropertyType.shared: "合租房间 / Shared accommodation",
}


def _money(value: dict | None) -> str:
    if not value:
        return "待确认 / To be confirmed"
    return f"{value.get('currency', '')} {value.get('decimal', '')}".strip()


class ContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _build_source_snapshot(self, booking: Booking) -> dict:
        tenant = await self.session.get(User, booking.tenant_id)
        landlord = await self.session.get(User, booking.landlord_id)
        property_obj = await self.session.get(Property, booking.property_id)
        if not property_obj:
            raise ValueError("Property not found")

        application = booking.application_data or {}
        personal = application.get("personal_info") or {}
        pricing = application.get("pricing_snapshot") or {}
        option = next(
            (item for item in pricing.get("options", []) if item.get("months") == booking.lease_months),
            None,
        )
        if option is None and booking.scheduled_date:
            calculated = LeasePricingService.calculate(
                property_obj, datetime.fromisoformat(booking.scheduled_date).date()
            ).model_dump(mode="json")
            pricing = calculated
            option = next(
                (item for item in pricing["options"] if item["months"] == booking.lease_months),
                None,
            )
        if option is None:
            raise ValueError("The booking has no valid pricing snapshot")

        prices = option["prices"]
        policy_rows = await self.session.scalars(
            select(PolicyConsent).where(PolicyConsent.booking_id == booking.id)
        )
        policy_versions = {item.policy_key: item.policy_version for item in policy_rows}
        property_rules = application.get("property_contract_rules") or {}
        included = property_rules.get("included_utilities") or []
        excluded = property_rules.get("excluded_utilities") or []
        utilities_text = {
            "zh": f"已包含：{'、'.join(included) if included else '房源记录未配置'}；不包含：{'、'.join(excluded) if excluded else '房源记录未配置'}。未列明费用以订单和房源规则为准。",
            "en": f"Included: {', '.join(included) if included else 'not configured in the property record'}; excluded: {', '.join(excluded) if excluded else 'not configured in the property record'}. Unlisted charges are governed by the booking and property rules.",
        }
        tenant_cn = personal.get("chinese_name") or (tenant.username if tenant else "待确认")
        tenant_en = " ".join(filter(None, [personal.get("given_name_pinyin"), personal.get("surname_pinyin")])) or "To be confirmed"
        commencement = booking.scheduled_date or "待确认"
        return {
            "development_notice": DEVELOPMENT_NOTICE,
            "order_number": str(booking.id),
            "provider_name": landlord.username if landlord else f"Provider account #{booking.landlord_id}",
            "platform_name": PLATFORM_NAME,
            "platform_role": PLATFORM_ROLE,
            "tenant_name_cn": tenant_cn,
            "tenant_name_en": tenant_en,
            "property_name": property_obj.title,
            "property_address": property_obj.address,
            "property_id": property_obj.id,
            "room_type": PROPERTY_TYPE_LABELS.get(property_obj.property_type, str(property_obj.property_type)),
            "occupancy_limit": property_rules.get("occupancy_limit") or max(1, property_obj.bedrooms or 1),
            "commencement_date": commencement,
            "expiry_date": option["end_date"],
            "tenancy_months": booking.lease_months,
            "monthly_rent": _money(prices["monthly_rent"]["local"]),
            "deposit": _money(prices["deposit"]["local"]),
            "service_fee": _money(prices["service_fee"]["local"]),
            "amount_due_now": _money(prices["amount_due_now"]["local"]),
            "future_rent": _money(prices["rent_total"]["local"]),
            "settlement_currency": pricing["local_currency"],
            "cny_reference_amount": _money(prices["amount_due_now"]["cny"]),
            "exchange_rate": pricing["exchange_rate_to_cny"],
            "exchange_rate_at": pricing["exchange_rate_at"],
            "exchange_rate_source": pricing["exchange_rate_source"],
            "tax_treatment": property_rules.get("tax_treatment") or "房源记录未配置 / Not configured in the property record",
            "utilities": utilities_text,
            "cancellation_policy_version": policy_versions.get("cancellation", "未记录 / Not recorded"),
            "privacy_policy_version": policy_versions.get("privacy", "未记录 / Not recorded"),
            "cross_border_policy_version": policy_versions.get("cross-border-data", "未记录 / Not recorded"),
            "governing_law": property_rules.get("governing_law") or "待房源所在地法务配置 / To be configured for the property jurisdiction",
            "dispute_resolution": property_rules.get("dispute_resolution") or "待房源所在地法务配置 / To be configured for the property jurisdiction",
            "prevailing_language": property_rules.get("prevailing_language") or "待业务和法务配置 / To be configured by business and legal counsel",
            "provider_execution_mode": property_rules.get("provider_execution_mode") or "待配置；不得视为供应方已签署或盖章 / Not configured; no provider signature or seal is represented",
        }

    @staticmethod
    def _sections(source: dict) -> list[dict]:
        return [
            {"number": 1, "title_zh": "合同主体与平台角色", "title_en": "Parties and Platform Role", "zh": f"房源供应方为“{source['provider_name']}”，租客为“{source['tenant_name_cn']}”。{source['platform_name']}的角色为{source['platform_role']}，除非订单明确另有约定，平台不作为出租方。", "en": f"The accommodation provider is “{source['provider_name']}” and the tenant is “{source['tenant_name_en']}”. {source['platform_name']} acts as {source['platform_role']} and is not the landlord unless the booking expressly states otherwise."},
            {"number": 2, "title_zh": "房源与租期", "title_en": "Property and Tenancy Term", "zh": f"房源为{source['property_name']}（编号 {source['property_id']}），地址为{source['property_address']}，房型为{source['room_type']}。租期自{source['commencement_date']}起至{source['expiry_date']}止，共{source['tenancy_months']}个月。", "en": f"The premises are {source['property_name']} (Property ID {source['property_id']}) at {source['property_address']}, room type {source['room_type']}. The tenancy runs from {source['commencement_date']} to {source['expiry_date']} for {source['tenancy_months']} month(s)."},
            {"number": 3, "title_zh": "租金、押金和费用", "title_en": "Rent, Deposit and Fees", "zh": f"月租为{source['monthly_rent']}，押金为{source['deposit']}，服务费为{source['service_fee']}，当前应付金额为{source['amount_due_now']}，租期租金合计为{source['future_rent']}。税费处理：{source['tax_treatment']}。", "en": f"Monthly rent is {source['monthly_rent']}, the deposit is {source['deposit']}, the service fee is {source['service_fee']}, the amount due now is {source['amount_due_now']}, and total rent for the term is {source['future_rent']}. Tax treatment: {source['tax_treatment']}."},
            {"number": 4, "title_zh": "水电网络及其他费用", "title_en": "Utilities and Other Charges", "zh": source["utilities"]["zh"], "en": source["utilities"]["en"]},
            {"number": 5, "title_zh": "房屋用途和入住人数", "title_en": "Permitted Use and Occupancy", "zh": f"房屋仅限合法居住用途，未经许可不得改变用途；入住人数不得超过 {source['occupancy_limit']} 人。", "en": f"The premises shall be used only for lawful residential purposes and not for any unauthorised purpose. Occupancy shall not exceed {source['occupancy_limit']} person(s)."},
            {"number": 6, "title_zh": "转租和转让", "title_en": "Assignment and Subletting", "zh": "未经房源供应方事先书面许可，租客不得转租、转让本协议或允许他人长期占用房屋。", "en": "The tenant shall not assign this agreement, sublet the premises or permit long-term occupation by another person without the provider’s prior written permission."},
            {"number": 7, "title_zh": "房屋维护、损坏和押金扣除", "title_en": "Maintenance, Damage and Deposit Deductions", "zh": "租客应合理使用房屋。正常损耗不由租客承担；因租客造成的损坏可从押金中扣除，但供应方应提供分项依据，并遵守当地强制性法律。", "en": "The tenant shall take reasonable care of the premises. Fair wear and tear is excluded from tenant liability. Deductions for tenant-caused damage require an itemised basis and remain subject to mandatory local law."},
            {"number": 8, "title_zh": "入室检查和维修", "title_en": "Access, Inspection and Repairs", "zh": "除紧急情况外，供应方进入房屋检查或维修通常应给予合理通知；所有进入安排均受房源所在地法律约束。", "en": "Except in emergencies, access for inspection or repairs should normally follow reasonable notice. All access remains subject to the law of the property jurisdiction."},
            {"number": 9, "title_zh": "行为规范", "title_en": "Conduct", "zh": "租客不得从事违法、危险、严重扰民或危害其他住户和房屋安全的行为，并应遵守已披露的房源规则。", "en": "The tenant shall not engage in unlawful, dangerous or seriously disruptive conduct and shall comply with disclosed property rules."},
            {"number": 10, "title_zh": "取消、退款和违约", "title_en": "Cancellation, Refund and Default", "zh": f"本订单适用租客已同意的退订政策版本 {source['cancellation_policy_version']}。退款和违约后果按该版本、订单约定及强制性法律处理，不承诺无条件退款。", "en": f"Cancellation policy version {source['cancellation_policy_version']} accepted for this booking applies. Refunds and default consequences follow that version, the booking and mandatory law; no unconditional refund is promised."},
            {"number": 11, "title_zh": "入住资格和证件", "title_en": "Eligibility and Documents", "zh": "租客应提供当地法律或房源供应方为核实身份和入住资格而合理要求的材料。", "en": "The tenant shall provide identity and eligibility documents reasonably required by applicable law or the accommodation provider."},
            {"number": 12, "title_zh": "隐私和跨境数据", "title_en": "Privacy and Cross-border Data", "zh": f"个人信息处理适用隐私政策版本 {source['privacy_policy_version']}；跨境信息处理适用授权版本 {source['cross_border_policy_version']}。", "en": f"Personal data is handled under privacy policy version {source['privacy_policy_version']}; cross-border processing is governed by authorisation version {source['cross_border_policy_version']}."},
            {"number": 13, "title_zh": "电子签名和电子记录", "title_en": "Electronic Signature and Records", "zh": "租客可通过平台电子签署；签署记录应与合同版本、内容哈希、租客账户和签署时间绑定。本模板不表示任何一方已经签署。", "en": "The tenant may execute this agreement electronically. Any signing record must bind the agreement version and hash to the tenant account and signing time. This template does not represent that any party has signed."},
            {"number": 14, "title_zh": "通知", "title_en": "Notices", "zh": "平台账户消息和订单登记邮箱为认可的通知渠道；法律要求其他送达方式的，从其规定。", "en": "In-account messages and the email registered for the booking are recognised notice channels, unless applicable law requires another method."},
            {"number": 15, "title_zh": "适用法律和争议解决", "title_en": "Governing Law and Dispute Resolution", "zh": f"适用法律：{source['governing_law']}。争议解决：{source['dispute_resolution']}。任何约定均不排除强制性消费者保护。", "en": f"Governing law: {source['governing_law']}. Dispute resolution: {source['dispute_resolution']}. Mandatory consumer protections are not excluded."},
            {"number": 16, "title_zh": "语言", "title_en": "Language", "zh": f"中英文文本具有对应关系。文本不一致时的优先语言规则为：{source['prevailing_language']}。", "en": f"The Chinese and English texts correspond. The prevailing-language rule is: {source['prevailing_language']}."},
            {"number": 17, "title_zh": "完整协议与可分割性", "title_en": "Entire Agreement and Severability", "zh": "本协议、订单价格快照、已披露房源规则及引用政策共同构成双方约定。部分条款无效不影响其余条款效力，但应受适用法律约束。", "en": "This agreement, the booking price snapshot, disclosed property rules and incorporated policies form the parties’ arrangement. Invalidity of one provision does not invalidate the remainder, subject to applicable law."},
        ]

    @classmethod
    def _plain_content(cls, snapshot: dict) -> str:
        lines = ["房屋预订及租赁协议", "Housing Reservation and Tenancy Agreement", DEVELOPMENT_NOTICE]
        for section in snapshot["sections"]:
            lines.extend([f"第{section['number']}条 {section['title_zh']}", section["zh"], f"Article {section['number']} {section['title_en']}", section["en"], ""])
        return "\n".join(lines)

    async def generate_contract(self, booking: Booking) -> Contract:
        source = await self._build_source_snapshot(booking)
        source_hash = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        latest = await self.session.scalar(
            select(Contract).where(Contract.booking_id == booking.id).order_by(Contract.version.desc())
        )
        if latest and (latest.snapshot or {}).get("source_hash") == source_hash:
            return latest

        version = (latest.version + 1) if latest else 1
        generated_at = datetime.now(timezone.utc)
        agreement_number = f"HRTA-{generated_at:%Y%m%d}-{booking.id:08d}-V{version}"
        snapshot = {
            **source,
            "source_hash": source_hash,
            "agreement_number": agreement_number,
            "agreement_version": version,
            "template_version": TEMPLATE_VERSION,
            "generated_at": generated_at.isoformat(),
        }
        snapshot["sections"] = self._sections(snapshot)
        content = self._plain_content(snapshot)
        content_hash = hashlib.sha256(
            (json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + content).encode()
        ).hexdigest()
        snapshot["content_hash"] = content_hash
        contract = Contract(
            booking_id=booking.id, tenant_id=booking.tenant_id, property_id=booking.property_id,
            template_name="housing_reservation_tenancy_bilingual", agreement_number=agreement_number,
            version=version, template_version=TEMPLATE_VERSION, content_hash=content_hash,
            snapshot=snapshot, generated_at=generated_at, content=content, status="generated",
        )
        self.session.add(contract)
        if booking.status not in {BookingStatus.cancelled, BookingStatus.rejected, BookingStatus.completed}:
            booking.status = BookingStatus.contract_ready
        if latest and latest.status == "signed":
            from app.services.order_notification_service import OrderNotificationService
            await OrderNotificationService(self.session).enqueue("contract_resign_required", booking, contract=contract, discriminator=str(version))
        await self.session.commit()
        await self.session.refresh(contract)
        return contract

    async def get_contract(self, contract_id: str) -> Contract | None:
        return await self.session.get(Contract, contract_id)

    async def list_by_booking(self, booking_id: int) -> Contract | None:
        return await self.session.scalar(
            select(Contract).where(Contract.booking_id == booking_id).order_by(Contract.version.desc())
        )

    async def sign_contract(self, contract_id: str) -> Contract | None:
        """保留既有签署接口兼容性；本阶段不扩展签名能力。"""
        contract = await self.session.get(Contract, contract_id)
        if not contract:
            return None
        contract.status = "signed"
        contract.signed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(contract)
        return contract
