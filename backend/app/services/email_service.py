import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP-based email service for sending notification emails."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def send(self, to_email: str, subject: str, html_body: str) -> dict:
        """Send an HTML email via SMTP.

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
            import asyncio
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._send_sync,
                smtp_host, smtp_port, smtp_user, smtp_password,
                from_email, [to_email], msg.as_string(),
                self.settings.smtp_use_tls,
            )
            logger.info("Email sent to %s", to_email)
            return {"status": "sent"}
        except Exception as exc:
            logger.exception("Email send error to %s", to_email)
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
