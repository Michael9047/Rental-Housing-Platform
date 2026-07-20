"""阿里云 DirectMail 邮件服务（SMTP fallback）。

发送邮件优先使用 DirectMail SDK（支持附件、模板），
未配置时自动降级到旧 SMTP 通道。
"""

import asyncio
import io
import logging
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 阿里云 DirectMail SDK（延迟导入，避免未安装时启动报错）
# ---------------------------------------------------------------------------
_DM_CLIENT = None
_DM_CLIENT_LOCK = asyncio.Lock()


def _get_dm_client():
    """延迟初始化 DirectMail 客户端（同步版本，线程安全）。

    只在 DirectMail 配置完整时才创建。首次调用后缓存，后续复用。
    """
    global _DM_CLIENT
    if _DM_CLIENT is not None:
        return _DM_CLIENT

    settings = get_settings()
    if not settings.dm_access_key_id or not settings.dm_account_name:
        return None

    try:
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_dm20151123.client import Client as Dm20151123Client

        config = open_api_models.Config(
            access_key_id=settings.dm_access_key_id,
            access_key_secret=settings.dm_access_key_secret,
        )
        config.endpoint = settings.dm_endpoint
        config.region_id = settings.dm_region_id
        _DM_CLIENT = Dm20151123Client(config)
        logger.info("DirectMail 客户端已初始化，endpoint=%s", settings.dm_endpoint)
        return _DM_CLIENT
    except Exception as exc:
        logger.warning("DirectMail SDK 初始化失败: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 类型定义
# ---------------------------------------------------------------------------


@dataclass
class Attachment:
    """邮件附件。"""

    filename: str       # 收件人看到的文件名，如 "租赁合同-阳光花园.pdf"
    content: bytes      # 文件二进制内容

    def to_base64(self) -> str:
        import base64
        return base64.b64encode(self.content).decode("ascii")


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------


class EmailService:
    """阿里云 DirectMail 邮件服务（SMTP fallback）。

    DirectMail 优先，未配置时自动降级到 SMTP。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    # ── 公共接口 ────────────────────────────────────────────────

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[list[Attachment]] = None,
        from_alias: Optional[str] = None,
    ) -> dict:
        """发送 HTML 邮件（可选附件）。

        自动选择 DirectMail > SMTP > skip 的降级路径。

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_body: HTML 正文
            attachments: 附件列表（仅 DirectMail 支持）
            from_alias: 发件人别名（覆盖配置中的默认值）

        Returns:
            {"status": "sent"|"skipped", ...}
        """
        if not to_email:
            return {"status": "skipped", "reason": "no email address"}

        # ── 1. DirectMail（优先）────────────────────────────────
        if self.settings.dm_access_key_id and self.settings.dm_account_name:
            return await self._send_via_directmail(
                to_email, subject, html_body, attachments, from_alias,
            )

        # ── 2. SMTP fallback ──────────────────────────────────
        if self.settings.smtp_host:
            logger.warning(
                "DirectMail 未配置，降级到 SMTP 发送（to=%s）", to_email,
            )
            if attachments:
                logger.warning(
                    "SMTP 不支持附件，跳过附件（%d 个）", len(attachments),
                )
            return await self._send_via_smtp(to_email, subject, html_body)

        # ── 3. 都未配置 ──────────────────────────────────────
        logger.warning("邮件服务未配置，跳过发送（to=%s）", to_email)
        return {"status": "skipped", "reason": "no email provider configured"}

    async def send_with_template(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict,
        attachments: Optional[list[Attachment]] = None,
        from_alias: Optional[str] = None,
    ) -> dict:
        """使用邮件模板发送。

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            template_name: 模板名称（不含 .html 后缀），如 "welcome"
            context: 模板变量字典
            attachments: 附件列表
            from_alias: 发件人别名

        Returns:
            {"status": "sent"|"skipped", ...}
        """
        from app.services.email_templates import render

        html_body = render(template_name, **context)
        return await self.send(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            attachments=attachments,
            from_alias=from_alias,
        )

    # ── DirectMail 私有方法 ────────────────────────────────────

    async def _send_via_directmail(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[list[Attachment]],
        from_alias: Optional[str],
    ) -> dict:
        """通过阿里云 DirectMail SDK 发送邮件。"""
        client = _get_dm_client()
        if client is None:
            logger.warning("DirectMail 客户端不可用，跳过发送（to=%s）", to_email)
            return {"status": "skipped", "reason": "directmail client unavailable"}

        from_name = from_alias or self.settings.dm_from_alias or "Rental Housing"
        account_name = self.settings.dm_account_name

        # 构建附件列表
        dm_attachments = self._build_attachments(attachments)

        try:
            from alibabacloud_dm20151123 import models as dm_models

            request = dm_models.SingleSendMailAdvanceRequest(
                account_name=account_name,
                address_type="1",            # 1=随机账号（触发类邮件）
                reply_to_address="true",     # 使用 account_name 作为回复地址
                to_address=to_email,
                subject=subject,
                html_body=html_body,
                from_alias=from_name,
                attachments=dm_attachments if dm_attachments else None,
            )

            from alibabacloud_tea_util import models as util_models

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.single_send_mail_advance(
                    request, util_models.RuntimeOptions(),
                ),
            )

            # response.body 是一个 SingleSendMailResponseBody
            body = response.body
            request_id = getattr(body, "request_id", "") if body else ""
            env_id = getattr(body, "env_id", "") if body else ""

            logger.info(
                "DirectMail 发送成功 to=%s request_id=%s env_id=%s",
                to_email, request_id, env_id,
            )
            return {
                "status": "sent",
                "provider": "directmail",
                "request_id": request_id,
                "env_id": env_id,
            }
        except Exception as exc:
            logger.exception("DirectMail 发送失败 to=%s: %s", to_email, exc)
            # DirectMail 失败时尝试 SMTP fallback
            if self.settings.smtp_host:
                logger.warning("DirectMail 失败，降级到 SMTP（to=%s）", to_email)
                return await self._send_via_smtp(to_email, subject, html_body)
            raise

    @staticmethod
    def _build_attachments(
        attachments: Optional[list[Attachment]],
    ) -> Optional[list]:
        """将内部 Attachment 列表转为 DirectMail SDK 附件对象列表。"""
        if not attachments:
            return None

        try:
            from alibabacloud_dm20151123 import models as dm_models

            result = []
            for att in attachments:
                dm_att = dm_models.SingleSendMailAdvanceRequestAttachments(
                    att.filename,
                    io.BytesIO(att.content),
                )
                result.append(dm_att)
            return result
        except Exception as exc:
            logger.warning("附件转换失败: %s", exc)
            return None

    # ── SMTP fallback（保留旧实现）─────────────────────────────

    async def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> dict:
        """通过 SMTP 发送邮件（旧通道，仅支持纯文本 HTML）。

        Returns dict with status and optional error info.
        Silently skips if SMTP is not configured or email is empty.
        """
        if not to_email:
            return {"status": "skipped", "reason": "no email address"}

        smtp_host = self.settings.smtp_host
        smtp_port = self.settings.smtp_port
        smtp_user = self.settings.smtp_user
        smtp_password = self.settings.smtp_password
        from_email = self.settings.smtp_from_email or smtp_user

        if not smtp_host or not smtp_user or not smtp_password:
            logger.warning("SMTP not configured, skipping email to %s", to_email)
            return {"status": "skipped", "reason": "smtp not configured"}

        from_name = self.settings.smtp_from_name or "Rental Housing"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._send_sync,
                smtp_host, smtp_port, smtp_user, smtp_password,
                from_email, [to_email], msg.as_string(),
                self.settings.smtp_use_tls,
            )
            logger.info("SMTP 发送成功 to=%s", to_email)
            return {"status": "sent", "provider": "smtp"}
        except Exception as exc:
            logger.exception("SMTP 发送失败 to=%s", to_email)
            raise

    @staticmethod
    def _send_sync(
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
        msg_string: str,
        use_tls: bool,
    ) -> None:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, to_addrs, msg_string)
