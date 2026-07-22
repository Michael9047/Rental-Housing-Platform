"""阿里云短信服务 (dysmsapi) —— 通知类短信。

与号码认证 (dypnsapi) 分离：前者发验证码，此服务发业务通知。
模板需在阿里云控制台提交审核，审核通过后拿到 TemplateCode 填入配置。
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from urllib.parse import quote

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 通知类型 → 模板变量构建器
# 每种通知类型需要的模板变量不同，在此集中定义。
# 模板变量名必须与阿里云控制台中申请的模板占位符一致。
# ---------------------------------------------------------------------------


def _build_template_param(
    title: str,
    content: str,
    **extra,
) -> dict:
    """通用模板变量构建器。

    默认传 title 和 content，子类可针对具体类型覆盖。
    返回的 dict 会被 JSON 序列化后作为 TemplateParam 发送。
    """
    return {"title": title, "content": content}


# 各通知类型的模板变量构建器（按需扩展）
_TEMPLATE_BUILDERS: dict[str, callable] = {
    # 示例 —— 当你有特定模板时取消注释：
    # "booking_created": lambda t, c, **kw: {
    #     "address": kw.get("address", ""),
    #     "status": kw.get("status", "已确认"),
    #     "time": kw.get("time", ""),
    # },
    # "payment_received": lambda t, c, **kw: {
    #     "order_sn": kw.get("order_sn", ""),
    #     "status": kw.get("status", "成功"),
    #     "amount": kw.get("amount", ""),
    # },
}


# ---------------------------------------------------------------------------
# NotificationSmsService
# ---------------------------------------------------------------------------


class NotificationSmsService:
    """阿里云短信服务 (dysmsapi) —— 业务通知短信。

    使用 SendSms API，支持自定义模板（需在控制台提前审核）。

    用法:
        svc = NotificationSmsService()
        result = await svc.send(
            phone_number="13800138000",
            notification_type="booking_created",
            title="预约确认",
            content="您的预约已确认",
        )
    """

    ENDPOINT = "dysmsapi.aliyuncs.com"
    API_VERSION = "2017-05-25"
    ACTION = "SendSms"

    def __init__(self) -> None:
        self.settings = get_settings()

    # ── 签名（与 dypnsapi 相同，阿里云 API v1 通用）─────────────

    @staticmethod
    def _sign(params: dict, secret: str) -> str:
        """生成阿里云 API v1 HMAC-SHA1 签名（POST 请求）。"""
        sorted_keys = sorted(params.keys())
        canonical = "&".join(
            f"{quote(k, safe='')}={quote(str(params[k]), safe='')}"
            for k in sorted_keys
        )
        string_to_sign = (
            f"POST&{quote('/', safe='')}&{quote(canonical, safe='')}"
        )
        signature = hmac.new(
            (secret + "&").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        import base64
        return base64.b64encode(signature).decode("utf-8")

    # ── 公共接口 ────────────────────────────────────────────────

    async def send(
        self,
        phone_number: str,
        notification_type: str,
        title: str = "",
        content: str = "",
        **template_kwargs,
    ) -> dict:
        """发送通知短信。

        Args:
            phone_number: 接收手机号
            notification_type: 通知类型，如 "booking_created"
            title: 通知标题（传给模板变量构建器）
            content: 通知正文（传给模板变量构建器）
            **template_kwargs: 额外的模板变量，如 address、time 等

        Returns:
            {"status": "sent", "biz_id": "..."}
            {"status": "skipped", "reason": "..."}
            {"status": "failed", "error": "..."}
        """
        if not phone_number:
            return {"status": "skipped", "reason": "no phone number"}

        # 查找该通知类型对应的模板CODE
        template_code = self._get_template_code(notification_type)
        if not template_code:
            logger.info(
                "通知类型 %s 未配置短信模板CODE，跳过发送", notification_type,
            )
            return {
                "status": "skipped",
                "reason": f"no template configured for {notification_type}",
            }

        access_key_id = self.settings.sms_notify_access_key_id
        access_key_secret = self.settings.sms_notify_access_key_secret
        sign_name = self.settings.sms_notify_sign_name

        if not access_key_id or not access_key_secret:
            logger.warning("通知短信未配置 AK，跳过发送 to %s", phone_number)
            return {"status": "skipped", "reason": "sms notify not configured"}

        # 构建模板变量
        builder = _TEMPLATE_BUILDERS.get(notification_type, _build_template_param)
        template_param = builder(title=title, content=content, **template_kwargs)

        return await self._send_sms(
            phone_number, sign_name, template_code, template_param,
            access_key_id, access_key_secret,
        )

    # ── 私有方法 ────────────────────────────────────────────────

    def _get_template_code(self, notification_type: str) -> str:
        """从配置的 JSON 映射中读取通知类型对应的模板CODE。"""
        try:
            mapping = json.loads(self.settings.sms_notify_template_map)
        except (json.JSONDecodeError, TypeError):
            logger.warning("sms_notify_template_map 解析失败")
            return ""
        return mapping.get(notification_type, "")

    async def _send_sms(
        self,
        phone_number: str,
        sign_name: str,
        template_code: str,
        template_param: dict,
        access_key_id: str,
        access_key_secret: str,
    ) -> dict:
        """调用 dysmsapi SendSms API。"""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        nonce = str(uuid.uuid4())

        params = {
            "AccessKeyId": access_key_id,
            "Action": self.ACTION,
            "Format": "JSON",
            "PhoneNumbers": phone_number,
            "SignName": sign_name,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": nonce,
            "SignatureVersion": "1.0",
            "TemplateCode": template_code,
            "TemplateParam": json.dumps(template_param, ensure_ascii=False),
            "Timestamp": timestamp,
            "Version": self.API_VERSION,
        }
        params["Signature"] = self._sign(params, access_key_secret)

        endpoint = self.settings.sms_notify_endpoint or self.ENDPOINT
        url = f"https://{endpoint}/"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=params, timeout=10.0)
                resp.raise_for_status()
                result = resp.json()
            if result.get("Code") == "OK":
                logger.info(
                    "通知短信已发送 to %s biz_id=%s template=%s",
                    phone_number, result.get("BizId"), template_code,
                )
                return {"status": "sent", "biz_id": result.get("BizId")}
            else:
                logger.error(
                    "通知短信发送失败 to %s: %s (code=%s)",
                    phone_number, result.get("Message"), result.get("Code"),
                )
                return {"status": "failed", "error": result.get("Message")}
        except Exception as exc:
            logger.exception("通知短信发送异常 to %s", phone_number)
            raise
