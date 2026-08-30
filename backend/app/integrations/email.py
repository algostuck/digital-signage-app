"""Email delivery adapter (P2-NTF-003; real SMTP added in P3 3E-2).

Dev/test use the logging provider — the message is recorded and counted as
delivered, mirroring how LocalStorage stands in for S3 (ADR-004).
`SmtpEmailProvider` is the production adapter, selected via
`EMAIL_BACKEND=smtp`; credentials come from environment configuration
(SMTP_* settings), never from the database. A per-tenant white-label
sender identity may override the From header (P3-GLO-003).
"""

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("app.email")


class LogEmailProvider:
    """Records outbound mail in the application log."""

    def send(
        self, *, to: str, subject: str, body: str, from_addr: str | None = None
    ) -> bool:
        logger.info(
            "EMAIL to=%s from=%s subject=%r body=%r", to, from_addr or "-", subject, body
        )
        return True


class SmtpEmailProvider:
    """Real SMTP delivery (P3 3E-2). STARTTLS by default; anonymous relay
    when no credentials are configured."""

    def send(
        self, *, to: str, subject: str, body: str, from_addr: str | None = None
    ) -> bool:
        from app.core.config import get_settings

        settings = get_settings()
        message = EmailMessage()
        message["To"] = to
        message["From"] = from_addr or settings.smtp_from
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
            return True
        except Exception:  # noqa: BLE001 — delivery evidence records the failure
            logger.exception("SMTP delivery to %s failed", to)
            return False


_provider: LogEmailProvider | SmtpEmailProvider | None = None


def get_email_provider() -> LogEmailProvider | SmtpEmailProvider:
    global _provider
    if _provider is None:
        from app.core.config import get_settings

        backend = getattr(get_settings(), "email_backend", "log")
        _provider = SmtpEmailProvider() if backend == "smtp" else LogEmailProvider()
    return _provider
