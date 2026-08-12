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
    "booking-authorization": Policy(
        key="booking-authorization",
        title="《订房授权书》",
        version=1,
        content_hash="booking_authorization_v1_hash",
        content="本人授权平台在本人确认的房源、入住日期和租期范围内，向房源供应方提交订房申请并同步必要的申请材料。",
    ),
    "cross-border-data": Policy(
        key="cross-border-data",
        title="《个人信息出境授权声明》",
        version=1,
        content_hash="cross_border_data_v1_hash",
        content="本人知悉并同意，为完成跨境公寓预订、合同生成和入住服务，平台可将必要个人信息提交给境外房源供应方。",
    ),
    "privacy": Policy(
        key="privacy",
        title="《隐私政策》",
        version=1,
        content_hash="privacy_v1_hash",
        content="平台仅在注册登录、房源推荐、预订履约、合同签署、支付通知和售后服务所需范围内处理个人信息。",
    ),
    "cancellation": Policy(
        key="cancellation",
        title="《公寓退订政策》",
        version=1,
        content_hash="cancellation_v1_hash",
        content="退订条件因国家或地区、房源、房型及价格方案而异，最终以订单确认页、合同和房源供应方规则为准。",
    ),
}
