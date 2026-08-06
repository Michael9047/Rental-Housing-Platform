import hashlib
import time
from dataclasses import dataclass
from urllib.parse import urlencode

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


@dataclass
class WeChatOAuthToken:
    """微信开放平台 OAuth2 access_token 响应"""
    openid: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 7200
    scope: str = "snsapi_login"
    unionid: str | None = None


class WeChatService:
    """WeChat Mini Program service for login, template messages, and access token management."""

    CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
    TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    SEND_TEMPLATE_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
    CUSTOMER_SERVICE_URL = "https://api.weixin.qq.com/cgi-bin/message/custom/send"

    # 微信开放平台 OAuth（Web 扫码登录）
    QR_CONNECT_URL = "https://open.weixin.qq.com/connect/qrconnect"
    OAUTH_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"

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

    # ── 微信开放平台 OAuth（Web 扫码登录）────────────────

    def get_qr_connect_url(self, redirect_uri: str, state: str) -> str:
        """生成微信开放平台扫码登录 URL"""
        params = {
            "appid": self.settings.wechat_open_appid,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snsapi_login",
            "state": state,
        }
        return f"{self.QR_CONNECT_URL}?{urlencode(params)}#wechat_redirect"

    async def exchange_qr_code(self, code: str) -> WeChatOAuthToken:
        """用 authorization_code 换取 openid（Web 扫码回调）"""
        if self.settings.wechat_open_dev_mode:
            return self._exchange_qr_code_dev(code)

        params = {
            "appid": self.settings.wechat_open_appid,
            "secret": self.settings.wechat_open_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.OAUTH_ACCESS_TOKEN_URL, params=params)
            resp.raise_for_status()
            data = await resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise ValueError(f"WeChat OAuth failed: {data.get('errmsg', 'unknown error')}")

        return WeChatOAuthToken(
            openid=data["openid"],
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in", 7200),
            scope=data.get("scope", "snsapi_login"),
            unionid=data.get("unionid"),
        )

    def _exchange_qr_code_dev(self, code: str) -> WeChatOAuthToken:
        """开发模式：用 code 的 hash 生成确定性 mock openid"""
        mock_openid = f"wx_open_mock_{hashlib.md5(code.encode()).hexdigest()[:16]}"
        return WeChatOAuthToken(
            openid=mock_openid,
            access_token="dev_access_token",
            expires_in=7200,
        )
