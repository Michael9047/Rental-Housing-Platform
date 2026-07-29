"""预订流程中租客必须接受的当前有效政策版本。"""
import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    key: str
    version: str
    content_hash: str
    title_zh: str
    title_en: str
    summary_zh: str


# 当前有效政策 — 修改内容后必须同步更新 version 和 content_hash
POLICIES: dict[str, Policy] = {
    "booking-authorization": Policy(
        key="booking-authorization",
        version="2026.1",
        content_hash=hashlib.sha256(
            json.dumps(
                {"key": "booking-authorization", "version": "2026.1", "text": "booking_authorization_policy_v1"},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        title_zh="订房授权书",
        title_en="Booking Authorization",
        summary_zh="租客授权平台代为预订指定房源，并同意按约定支付押金和租金。",
    ),
    "cancellation": Policy(
        key="cancellation",
        version="2026.1",
        content_hash=hashlib.sha256(
            json.dumps(
                {"key": "cancellation", "version": "2026.1", "text": "cancellation_policy_v1"},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        title_zh="取消与退款政策",
        title_en="Cancellation & Refund Policy",
        summary_zh="租客在起租日前取消可退还押金，服务费按取消时间阶梯扣除。",
    ),
    "privacy": Policy(
        key="privacy",
        version="2026.1",
        content_hash=hashlib.sha256(
            json.dumps(
                {"key": "privacy", "version": "2026.1", "text": "privacy_policy_v1"},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        title_zh="隐私政策",
        title_en="Privacy Policy",
        summary_zh="平台仅收集预订必需的个⼈信息，不与第三方共享。",
    ),
    "cross-border-data": Policy(
        key="cross-border-data",
        version="2026.1",
        content_hash=hashlib.sha256(
            json.dumps(
                {"key": "cross-border-data", "version": "2026.1", "text": "cross_border_data_policy_v1"},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        title_zh="跨境数据传输授权",
        title_en="Cross-Border Data Transfer Authorization",
        summary_zh="预订跨境房源需授权将个⼈信息传输至房源所在国家/地区。",
    ),
}
