"""Email delivery adapter (P2-NTF-003).

Dev/test use the logging provider — the message is recorded and counted as
delivered, mirroring how LocalStorage stands in for S3 (ADR-004). A real
SMTP/SES provider implements the same two-method contract and is selected
via EMAIL_BACKEND at deployment time; no rule-engine code changes.
"""

import logging

logger = logging.getLogger("app.email")


class LogEmailProvider:
    """Records outbound mail in the application log."""

    def send(self, *, to: str, subject: str, body: str) -> bool:
        logger.info("EMAIL to=%s subject=%r body=%r", to, subject, body)
        return True


_provider: LogEmailProvider | None = None


def get_email_provider() -> LogEmailProvider:
    global _provider
    if _provider is None:
        _provider = LogEmailProvider()
    return _provider
