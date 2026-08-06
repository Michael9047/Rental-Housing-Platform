"""政策文档服务——提供预订流程所需的政策条款。"""
from dataclasses import dataclass


@dataclass
class Policy:
    key: str
    title: str
    version: int
    content_hash: str
    content: str = ""


POLICIES: dict[str, Policy] = {
    "booking_auth": Policy(
        key="booking_auth",
        title="订房授权书",
        version=1,
        content_hash="booking_auth_v1_hash",
        content="授权平台代为办理房源预订相关事宜。",
    ),
    "data_transfer": Policy(
        key="data_transfer",
        title="个人信息出境授权声明",
        version=1,
        content_hash="data_transfer_v1_hash",
        content="授权将个人信息跨境提交给房源供应方。",
    ),
    "cancellation": Policy(
        key="cancellation",
        title="公寓退订政策",
        version=1,
        content_hash="cancellation_v1_hash",
        content="退订政策细则。",
    ),
    "privacy": Policy(
        key="privacy",
        title="隐私政策",
        version=1,
        content_hash="privacy_v1_hash",
        content="平台将严格保护您的个人信息，未经授权不会向第三方披露。",
    ),
    "payment_service": Policy(
        key="payment_service",
        title="支付服务说明",
        version=1,
        content_hash="payment_service_v1_hash",
        content="本平台采用第三方支付服务，支付过程中产生的费用由支付服务提供商收取。",
    ),
}
