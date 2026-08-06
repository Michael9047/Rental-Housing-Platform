"""预订流程所需的政策文档注册表。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    """政策的展示和留存版本。"""
    key: str
    title_zh: str
    version: str
    content_hash: str
    summary_zh: str


POLICIES: dict[str, Policy] = {
    "booking_auth": Policy("booking_auth", "《预订及押金规则》", "1.0", "booking_auth_v1_hash", "预订押金用于锁定申请，并按正式规则抵扣租赁押金。支付成功不代表预订成功，平台仍须核验房源状态、申请资料及合同条件。"),
    "privacy": Policy("privacy", "《隐私政策》", "1.0", "privacy_v1_hash", "平台仅为处理预订、履行合同和依法合规之目的处理个人信息。敏感信息将按适用的个人信息保护规则处理。"),
    "data_transfer": Policy("data_transfer", "《个人信息出境授权声明》", "1.0", "data_transfer_v1_hash", "为协助申请境外房源，平台可在必要范围内向房源供应方传递本次申请所需信息；请在阅读后自主确认。"),
    "cancellation": Policy("cancellation", "《支付服务说明》", "1.0", "cancellation_v1_hash", "支付服务将展示支付方式、币种、汇率和可能适用的手续费。支付成功仅代表平台收到款项并受理预订申请；退款和取消按适用的正式规则处理。"),
}
