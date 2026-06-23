"""Tests for WeChat login, phone binding, and template message functionality."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.services.wechat_service import WeChatService


class TestWeChatService:
    """Unit tests for WeChatService."""

    def _make_response(self, json_data: dict):
        """Create a mock httpx response that has an async json method."""
        resp = AsyncMock()
        resp.json = AsyncMock(return_value=json_data)
        resp.raise_for_status = lambda: None
        return resp

    @pytest.mark.asyncio
    async def test_jscode2session_success(self):
        """Test successful code2session exchange."""
        mock_resp = self._make_response({
            "openid": "test_openid_123",
            "session_key": "test_session_key_456",
        })

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            service = WeChatService()
            object.__setattr__(service.settings, "wechat_appid", "test_appid")
            object.__setattr__(service.settings, "wechat_secret", "test_secret")

            session = await service.jscode2session("test_code")
            assert session.openid == "test_openid_123"
            assert session.session_key == "test_session_key_456"

    @pytest.mark.asyncio
    async def test_jscode2session_failure(self):
        """Test code2session with error response."""
        mock_resp = self._make_response({
            "errcode": 40029,
            "errmsg": "invalid code",
        })

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            service = WeChatService()
            object.__setattr__(service.settings, "wechat_appid", "test_appid")
            object.__setattr__(service.settings, "wechat_secret", "test_secret")

            with pytest.raises(ValueError, match="invalid code"):
                await service.jscode2session("bad_code")

    @pytest.mark.asyncio
    async def test_get_access_token_success(self):
        """Test access token retrieval with caching."""
        mock_resp = self._make_response({
            "access_token": "test_access_token_789",
            "expires_in": 7200,
        })

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            service = WeChatService()
            object.__setattr__(service.settings, "wechat_appid", "test_appid")
            object.__setattr__(service.settings, "wechat_secret", "test_secret")

            token = await service.get_access_token()
            assert token == "test_access_token_789"
            # Second call should use cache
            token2 = await service.get_access_token()
            assert token2 == "test_access_token_789"

    @pytest.mark.asyncio
    async def test_send_template_message_success(self):
        """Test sending template message."""
        token_resp = AsyncMock()
        token_resp.json = AsyncMock(return_value={
            "access_token": "test_token",
            "expires_in": 7200,
        })
        token_resp.raise_for_status = lambda: None

        send_resp = AsyncMock()
        send_resp.json = AsyncMock(return_value={
            "errcode": 0,
            "errmsg": "ok",
            "msgid": 12345,
        })
        send_resp.raise_for_status = lambda: None

        with patch("httpx.AsyncClient.get", return_value=token_resp), \
             patch("httpx.AsyncClient.post", return_value=send_resp):
            service = WeChatService()
            object.__setattr__(service.settings, "wechat_appid", "test_appid")
            object.__setattr__(service.settings, "wechat_secret", "test_secret")

            result = await service.send_template_message(
                openid="test_openid",
                template_id="template_1",
                data={"keyword1": {"value": "test"}},
            )
            assert result["msgid"] == 12345


class TestWeChatLoginAPI:
    """Integration tests for WeChat login API endpoints."""

    def _make_response(self, json_data: dict):
        """Create a mock httpx response that has an async json method."""
        resp = AsyncMock()
        resp.json = AsyncMock(return_value=json_data)
        resp.raise_for_status = lambda: None
        return resp

    @pytest.mark.asyncio
    async def test_wechat_login_new_user(self, client: AsyncClient):
        """Test WeChat login creates a new user."""
        mock_resp = self._make_response({
            "openid": "new_openid_abc",
            "session_key": "sk_abc",
        })

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            response = await client.post(
                "/api/v1/auth/wechat/login",
                json={"code": "test_code_new"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["is_new_user"] is True
        assert data["user"]["wechat_openid"] == "new_openid_abc"

    @pytest.mark.asyncio
    async def test_wechat_login_existing_user(self, client: AsyncClient):
        """Test WeChat login returns existing user."""
        mock_resp = self._make_response({
            "openid": "existing_openid",
            "session_key": "sk_existing",
        })

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            await client.post(
                "/api/v1/auth/wechat/login",
                json={"code": "code_first"},
            )

        # Second login with same openid
        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            response = await client.post(
                "/api/v1/auth/wechat/login",
                json={"code": "code_second"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_new_user"] is False
        assert data["user"]["wechat_openid"] == "existing_openid"

    @pytest.mark.asyncio
    async def test_wechat_login_invalid_code(self, client: AsyncClient):
        """Test WeChat login with invalid code returns 400."""
        mock_resp = self._make_response({
            "errcode": 40029,
            "errmsg": "invalid code",
        })

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            response = await client.post(
                "/api/v1/auth/wechat/login",
                json={"code": "bad_code"},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_wechat_config(self, client: AsyncClient):
        """Test wechat config endpoint returns appid."""
        response = await client.get("/api/v1/wechat/config")
        assert response.status_code == 200
        data = response.json()
        assert "appid" in data
