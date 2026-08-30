import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.context import request_id_ctx, tenant_id_ctx, user_id_ctx


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id := request_id_ctx.get():
            payload["request_id"] = request_id
        if tenant_id := tenant_id_ctx.get():
            payload["tenant_id"] = str(tenant_id)
        if user_id := user_id_ctx.get():
            payload["user_id"] = str(user_id)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_ctx.get()
        prefix = f"[{rid[:8]}] " if rid else ""
        return (
            f"{self.formatTime(record)} {record.levelname:8} "
            f"{prefix}{record.name}: {record.getMessage()}"
        )


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else PlainFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)
