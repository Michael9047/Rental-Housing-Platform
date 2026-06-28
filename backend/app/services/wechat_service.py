import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class WeChatSession:
    openid: str
    session_key: str
    unionid: str | None = None


@dataclass
class WeChatPhoneInfo:
    phone_number: str
    pure_phone_number: str
    country_code: str


class WeChatService:
    """WeChat Mini Program service for login, template messages, and access token management."""

    CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
    TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    SEND_TEMPLATE_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
    CUSTOMER_SERVICE_URL = "https://api.weixin.qq.com/cgi-bin/message/custom/send"

    _access_token: str | None = None
    _token_expires_at: float = 0.0

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def appid(self) -> str:
        return self.settings.wechat_appid

    @property
    def secret(self) -> str:
        return self.settings.wechat_secret

    async def jscode2session(self, code: str) -> WeChatSession:
        """Exchange wx.login() code for openid and session_key."""
        params = {
            "appid": self.appid,
            "secret": self.secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.CODE2SESSION_URL, params=params)
            resp.raise_for_status()
            data = await resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise ValueError(f"WeChat login failed: {data.get('errmsg', 'unknown error')}")

        return WeChatSession(
            openid=data["openid"],
            session_key=data["session_key"],
            unionid=data.get("unionid"),
        )

    async def get_access_token(self) -> str:
        """Get or refresh WeChat access token with automatic caching."""
        now = time.time()
        if self._access_token and now < self._token_expires_at - 300:
            return self._access_token

        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.secret,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.TOKEN_URL, params=params)
            resp.raise_for_status()
            data = await resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise ValueError(f"Failed to get access token: {data.get('errmsg', 'unknown error')}")

        self._access_token = data["access_token"]
        self._token_expires_at = now + data.get("expires_in", 7200)
        return self._access_token

    async def send_template_message(
        self,
        openid: str,
        template_id: str,
        data: dict,
        page: str | None = None,
        miniprogram_state: str = "formal",
    ) -> dict:
        """Send a WeChat template message to a user."""
        access_token = await self.get_access_token()
        params = {"access_token": access_token}

        body = {
            "touser": openid,
            "template_id": template_id,
            "data": data,
            "miniprogram_state": miniprogram_state,
        }
        if page:
            body["page"] = page

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.SEND_TEMPLATE_URL, params=params, json=body)
            resp.raise_for_status()
            result = await resp.json()

        if result.get("errcode", 0) != 0:
            raise ValueError(f"Template message failed: {result.get('errmsg', 'unknown error')}")

        return result

    async def send_customer_service_message(
        self,
        openid: str,
        msgtype: str,
        content: dict,
    ) -> dict:
        """Send a customer service message to a user."""
        access_token = await self.get_access_token()
        params = {"access_token": access_token}

        body = {
            "touser": openid,
            "msgtype": msgtype,
            msgtype: content,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.CUSTOMER_SERVICE_URL, params=params, json=body)
            resp.raise_for_status()
            result = await resp.json()

        if result.get("errcode", 0) != 0:
            raise ValueError(f"Customer service message failed: {result.get('errmsg', 'unknown error')}")

        return result
