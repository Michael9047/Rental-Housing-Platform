"""Dropbox Sign 嵌入式签署服务，所有密钥仅在服务端环境变量中使用。"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import get_settings


class DropboxSignError(Exception):
    """向调用方暴露的、不会包含供应商敏感响应内容的异常。"""


class DropboxSignService:
    base_url = "https://api.hellosign.com/v3"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _auth(self, *, require_client_id: bool = False) -> httpx.BasicAuth:
        """构造服务端 Basic Auth；模板读取只需要 API Key。"""
        if not self.settings.dropbox_sign_api_key:
            raise DropboxSignError("Dropbox Sign API Key 尚未配置")
        if require_client_id and not self.settings.dropbox_sign_client_id:
            raise DropboxSignError("Dropbox Sign 尚未完成服务端配置")
        return httpx.BasicAuth(self.settings.dropbox_sign_api_key, "")

    async def list_templates(self, *, query: str | None = None) -> list[dict[str, Any]]:
        """读取当前服务账号有权访问的模板，仅返回绑定页面需要的非敏感摘要。"""
        params: dict[str, Any] = {"page": 1, "page_size": 100}
        if query:
            params["query"] = query
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.base_url}/template/list", params=params, auth=self._auth()
                )
            response.raise_for_status()
            templates = response.json().get("templates", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise DropboxSignError("无法读取 Dropbox Sign 模板列表") from exc
        if not isinstance(templates, list):
            raise DropboxSignError("Dropbox Sign 返回的模板列表无效")
        return [
            {
                "template_id": item.get("template_id"),
                "title": item.get("title"),
                "signer_roles": [
                    role.get("name") for role in item.get("signer_roles", [])
                    if isinstance(role, dict) and role.get("name")
                ],
            }
            for item in templates
            if isinstance(item, dict) and item.get("template_id")
        ]

    async def create_embedded_request(
        self,
        *,
        template_id: str,
        signer_role: str,
        signer_name: str,
        signer_email: str,
        custom_fields: Mapping[str, str],
        metadata: Mapping[str, str],
    ) -> dict[str, Any]:
        """以模板创建嵌入式签署请求，不向日志写入密钥或个人资料。"""
        payload = {
            "client_id": self.settings.dropbox_sign_client_id,
            "template_ids": [template_id],
            "signers": [{"role": signer_role, "name": signer_name, "email_address": signer_email}],
            "custom_fields": [
                {"name": name, "value": value} for name, value in custom_fields.items()
            ],
            "metadata": dict(metadata),
            "populate_auto_fill_fields": True,
            "test_mode": self.settings.dropbox_sign_test_mode,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.base_url}/signature_request/create_embedded_with_template",
                    json=payload,
                    auth=self._auth(require_client_id=True),
                )
            response.raise_for_status()
            data = response.json().get("signature_request", {})
        except (httpx.HTTPError, ValueError) as exc:
            raise DropboxSignError("无法创建 Dropbox Sign 签署请求") from exc
        if not data.get("signature_request_id") or not data.get("signatures"):
            raise DropboxSignError("Dropbox Sign 返回的签署请求无效")
        return data

    async def get_embedded_sign_url(self, signature_id: str) -> dict[str, Any]:
        """为指定签署人取得短时有效的嵌入页面地址。"""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.base_url}/embedded/sign_url/{signature_id}", auth=self._auth(require_client_id=True)
                )
            response.raise_for_status()
            data = response.json().get("embedded", {})
        except (httpx.HTTPError, ValueError) as exc:
            raise DropboxSignError("无法获取 Dropbox Sign 嵌入签署地址") from exc
        if not data.get("sign_url"):
            raise DropboxSignError("Dropbox Sign 未返回嵌入签署地址")
        return data

    async def download_signed_pdf(self, signature_request_id: str) -> bytes:
        """下载 Dropbox 已完成签署请求的合并 PDF，供平台私有归档。"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/signature_request/files/{signature_request_id}",
                    params={"file_type": "pdf"}, auth=self._auth(),
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                raise DropboxSignError("Dropbox Sign 正在准备已签署 PDF") from exc
            raise DropboxSignError("无法下载 Dropbox Sign 已签署 PDF") from exc
        except httpx.HTTPError as exc:
            raise DropboxSignError("无法下载 Dropbox Sign 已签署 PDF") from exc
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type or not response.content:
            raise DropboxSignError("Dropbox Sign 返回的已签署文件不是 PDF")
        return response.content

    def verify_event(self, event: Mapping[str, Any]) -> bool:
        """按 Dropbox Sign 文档校验回调事件摘要。"""
        supplied_hash = str(event.get("event_hash", ""))
        event_time = str(event.get("event_time", ""))
        event_type = str(event.get("event_type", ""))
        if not supplied_hash or not event_time or not event_type or not self.settings.dropbox_sign_api_key:
            return False
        expected_hash = hmac.new(
            self.settings.dropbox_sign_api_key.encode(),
            f"{event_time}{event_type}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(supplied_hash, expected_hash)
