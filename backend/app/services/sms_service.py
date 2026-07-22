import hashlib
import hmac
import logging
import time
import uuid
from urllib.parse import quote

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SmsService:
    """阿里云号码认证服务 (dypnsapi) —— 仅用于发送短信验证码。

    注意：此服务不支持通知类短信。如需发送"预约确认""支付提醒"等通知短信，
    请使用阿里云短信服务 (dysmsapi)，另建 NotificationSmsService。
    """

    ENDPOINT = "dypnsapi.aliyuncs.com"
    API_VERSION = "2017-05-25"
    ACTION = "SendSmsVerifyCode"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _sign(self, params: dict, secret: str) -> str:
        """生成阿里云 API v1 HMAC-SHA1 签名（POST 请求）。"""
        sorted_keys = sorted(params.keys())
        canonical = "&".join(
            f"{quote(k, safe='')}={quote(str(params[k]), safe='')}"
            for k in sorted_keys
        )
        string_to_sign = f"POST&{quote('/', safe='')}&{quote(canonical, safe='')}"
        signature = hmac.new(
            (secret + "&").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        import base64
        return base64.b64encode(signature).decode("utf-8")

    async def send_verification_code(
        self, phone_number: str, code: str, ttl_minutes: int = 5,
    ) -> dict:
        """发送短信验证码（阿里云号码认证 SendSmsVerifyCode）。

        Args:
            phone_number: 接收手机号
            code: 6 位数字验证码
            ttl_minutes: 验证码有效分钟数

        Returns:
            {"status": "sent", "biz_id": "..."}
            {"status": "skipped", "reason": "..."}
            {"status": "failed", "error": "..."}

        未配置 AK/Secret 时静默跳过，不发短信也不抛异常。
        """
        if not phone_number:
            return {"status": "skipped", "reason": "no phone number"}

        access_key_id = self.settings.sms_access_key_id
        access_key_secret = self.settings.sms_access_key_secret
        sign_name = self.settings.sms_sign_name
        template_code = self.settings.sms_template_code
        scheme_name = self.settings.sms_scheme_name

        if not access_key_id or not access_key_secret:
            logger.warning("短信验证码未配置 AK，跳过发送 to %s", phone_number)
            return {"status": "skipped", "reason": "sms not configured"}

        import json
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        nonce = str(uuid.uuid4())

        template_param = json.dumps({"code": code, "min": str(ttl_minutes)}, ensure_ascii=False)

        params = {
            "AccessKeyId": access_key_id,
            "Action": self.ACTION,
            "Format": "JSON",
            "PhoneNumber": phone_number,
            "SignName": sign_name,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": nonce,
            "SignatureVersion": "1.0",
            "SchemeName": scheme_name,
            "TemplateCode": template_code,
            "TemplateParam": template_param,
            "Timestamp": timestamp,
            "Version": self.API_VERSION,
        }
        params["Signature"] = self._sign(params, access_key_secret)

        endpoint = self.settings.sms_endpoint or self.ENDPOINT
        url = f"https://{endpoint}/"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=params, timeout=10.0)
                resp.raise_for_status()
                result = resp.json()
            if result.get("Code") == "OK":
                logger.info("验证码短信已发送 to %s biz_id=%s", phone_number, result.get("BizId"))
                return {"status": "sent", "biz_id": result.get("BizId")}
            else:
                logger.error("验证码短信发送失败 to %s: %s", phone_number, result.get("Message"))
                return {"status": "failed", "error": result.get("Message")}
        except Exception as exc:
            logger.exception("验证码短信发送异常 to %s", phone_number)
            raise
