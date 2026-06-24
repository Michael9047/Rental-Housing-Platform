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
    """Alibaba Cloud SMS service for sending SMS notifications."""

    ENDPOINT = "dysmsapi.aliyuncs.com"
    API_VERSION = "2017-05-25"
    ACTION = "SendSms"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _sign(self, params: dict, secret: str) -> str:
        """Generate Alibaba Cloud API v1 HMAC-SHA1 signature."""
        sorted_keys = sorted(params.keys())
        canonical = "&".join(
            f"{quote(k, safe='')}={quote(str(params[k]), safe='')}"
            for k in sorted_keys
        )
        string_to_sign = f"GET&{quote('/', safe='')}&{quote(canonical, safe='')}"
        signature = hmac.new(
            (secret + "&").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        import base64
        return base64.b64encode(signature).decode("utf-8")

    async def send(self, phone_number: str, template_param: dict | None = None) -> dict:
        """Send an SMS via Alibaba Cloud SMS API.

        Returns dict with status and optional error info.
        Silently skips if SMS is not configured or phone is empty.
        """
        if not phone_number:
            return {"status": "skipped", "reason": "no phone number"}

        access_key_id = self.settings.sms_access_key_id
        access_key_secret = self.settings.sms_access_key_secret
        sign_name = self.settings.sms_sign_name
        template_code = self.settings.sms_template_code

        if not access_key_id or not access_key_secret:
            logger.warning("SMS not configured, skipping send to %s", phone_number)
            return {"status": "skipped", "reason": "sms not configured"}

        import json
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
            "TemplateParam": json.dumps(template_param or {}),
            "Timestamp": timestamp,
            "Version": self.API_VERSION,
        }
        params["Signature"] = self._sign(params, access_key_secret)

        endpoint = self.settings.sms_endpoint or self.ENDPOINT
        url = f"https://{endpoint}/"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10.0)
                resp.raise_for_status()
                result = resp.json()
            if result.get("Code") == "OK":
                logger.info("SMS sent to %s: %s", phone_number, result.get("BizId"))
                return {"status": "sent", "biz_id": result.get("BizId")}
            else:
                logger.error("SMS failed to %s: %s", phone_number, result.get("Message"))
                return {"status": "failed", "error": result.get("Message")}
        except Exception as exc:
            logger.exception("SMS send error to %s", phone_number)
            raise
