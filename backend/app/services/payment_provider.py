"""多支付服务商统一接口；本地仅启用不采集卡信息的模拟托管收银台。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import hmac
import json
from typing import Any
import re

from app.core.config import get_settings


_SENSITIVE_FIELD_PATTERN = re.compile(r"(secret|key|certificate|private|card|pan|cvv|cvc|track|otp|authorization)", re.I)


def redact_payment_log_data(value: Any) -> Any:
    """供支付日志使用的递归脱敏器；webhook 正文默认完全不记录。"""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SENSITIVE_FIELD_PATTERN.search(str(key)) else redact_payment_log_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payment_log_data(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?<!\d)\d{12,19}(?!\d)", "[REDACTED_PAN]", value)
    return value


class PaymentMethod(StrEnum):
    WECHAT_PAY = "WECHAT_PAY"
    ALIPAY = "ALIPAY"
    CARD_CHECKOUT = "CARD_CHECKOUT"


@dataclass(frozen=True)
class PaymentRequest:
    order_id: str
    payment_attempt_id: str
    amount_minor: int
    settlement_currency: str
    expires_at: str
    idempotency_key: str
    description: str


@dataclass(frozen=True)
class CheckoutSession:
    provider_payment_id: str
    provider_checkout_id: str
    checkout_url: str
    merchant_account: str
    payment_method: PaymentMethod = PaymentMethod.CARD_CHECKOUT
    qr_code_url: str | None = None


@dataclass(frozen=True)
class RefundResult:
    provider_refund_id: str
    status: str


@dataclass(frozen=True)
class ProviderAvailability:
    method: PaymentMethod
    available: bool
    test_mode: bool
    reason: str | None = None


class ProviderUnavailableError(RuntimeError):
    pass


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> CheckoutSession: ...

    @abstractmethod
    def query_payment(self, provider_payment_id: str) -> str: ...

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str, headers: dict[str, str] | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def close_payment(self, provider_payment_id: str) -> bool: ...

    @abstractmethod
    def refund_payment(self, provider_payment_id: str, amount_minor: int, idempotency_key: str) -> RefundResult: ...

    @abstractmethod
    def query_refund(self, provider_refund_id: str) -> str: ...


class MockHostedPaymentProvider(PaymentProvider):
    """动态生成逐笔测试会话，不接收银行卡号、验证码或个人收款码。"""

    name = "mock_hosted"

    def __init__(self, payment_method: PaymentMethod = PaymentMethod.CARD_CHECKOUT) -> None:
        settings = get_settings()
        self.secret = settings.payment_mock_webhook_secret.encode()
        self.merchant = settings.payment_mock_merchant_account
        self.payment_method = payment_method

    def create_payment(self, request: PaymentRequest) -> CheckoutSession:
        checkout_id = f"mck_{request.payment_attempt_id.replace('-', '')[:24]}"
        # 二维码类方式同样指向逐笔动态测试会话，二维码图片由前端基于该 URL 渲染。
        checkout_url = f"/api/v1/payments/mock-checkout/{checkout_id}"
        qr_url = checkout_url if self.payment_method in {PaymentMethod.WECHAT_PAY, PaymentMethod.ALIPAY} else None
        return CheckoutSession(
            f"mpi_{request.payment_attempt_id}", checkout_id, checkout_url,
            self.merchant, self.payment_method, qr_url,
        )

    def create_checkout(self, payment_id: str) -> CheckoutSession:
        """兼容旧调用；新代码必须传入包含后端金额的 PaymentRequest。"""
        return self.create_payment(PaymentRequest(
            order_id=payment_id, payment_attempt_id=payment_id, amount_minor=0,
            settlement_currency="CNY", expires_at="", idempotency_key=payment_id,
            description="local test",
        ))

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify_webhook(self, payload: bytes, signature: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        expected = self.sign(payload)
        if not signature or not hmac.compare_digest(expected, signature):
            raise ValueError("Webhook signature verification failed")
        return json.loads(payload)

    def query_payment(self, provider_payment_id: str) -> str:
        return "pending"

    def close_payment(self, provider_payment_id: str) -> bool:
        return True

    def refund_payment(self, provider_payment_id: str, amount_minor: int, idempotency_key: str) -> RefundResult:
        return RefundResult(f"mock_refund_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]}", "succeeded")

    def query_refund(self, provider_refund_id: str) -> str:
        return "succeeded"


class MerchantApiProvider(PaymentProvider):
    """真实商户适配器安全基类；缺配置或未开启 live 时绝不发起网络付款。"""

    method: PaymentMethod

    def __init__(self) -> None:
        self.settings = get_settings()

    def _disabled(self) -> None:
        raise ProviderUnavailableError("该支付方式暂未开通")

    def create_payment(self, request: PaymentRequest) -> CheckoutSession: self._disabled()
    def query_payment(self, provider_payment_id: str) -> str: self._disabled()
    def verify_webhook(self, payload: bytes, signature: str, headers: dict[str, str] | None = None) -> dict[str, Any]: self._disabled()
    def close_payment(self, provider_payment_id: str) -> bool: self._disabled()
    def refund_payment(self, provider_payment_id: str, amount_minor: int, idempotency_key: str) -> RefundResult: self._disabled()
    def query_refund(self, provider_refund_id: str) -> str: self._disabled()


class WeChatPayProvider(MerchantApiProvider):
    name = "wechat_pay"
    method = PaymentMethod.WECHAT_PAY


class AlipayProvider(MerchantApiProvider):
    name = "alipay"
    method = PaymentMethod.ALIPAY


class CardCheckoutProvider(MerchantApiProvider):
    name = "card_checkout"
    method = PaymentMethod.CARD_CHECKOUT


def provider_availability() -> list[ProviderAvailability]:
    """测试环境展示三种模拟方式；生产环境必须同时满足开关和完整配置。"""
    settings = get_settings()
    if not settings.payments_live_enabled:
        test_mode = settings.environment.lower() != "production"
        return [ProviderAvailability(method, test_mode, test_mode, None if test_mode else "暂未开通") for method in PaymentMethod]
    configured = {
        PaymentMethod.WECHAT_PAY: all((settings.wechat_pay_merchant_id, settings.wechat_pay_app_id, settings.wechat_pay_api_v3_key, settings.wechat_pay_cert_serial_no, settings.wechat_pay_private_key_path, settings.wechat_pay_notify_url)),
        PaymentMethod.ALIPAY: all((settings.alipay_app_id, settings.alipay_private_key_path, settings.alipay_public_key_path, settings.alipay_notify_url, settings.alipay_return_url)),
        PaymentMethod.CARD_CHECKOUT: all((settings.card_provider, settings.card_secret_key, settings.card_publishable_key, settings.card_webhook_secret, settings.card_success_url, settings.card_cancel_url)),
    }
    # 商户 SDK/公网回调验收完成前适配器仍明确不可用，绝不伪装成已开通。
    return [ProviderAvailability(method, False, False, "商户适配器待完成审核与联调" if configured[method] else "暂未开通") for method in PaymentMethod]


def get_test_provider(method: PaymentMethod) -> PaymentProvider:
    settings = get_settings()
    if settings.environment.lower() == "production" or settings.payments_live_enabled:
        raise ProviderUnavailableError("生产环境不能使用模拟支付")
    return MockHostedPaymentProvider(method)
