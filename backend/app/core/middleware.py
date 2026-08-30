import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.core.context import client_ip_ctx, request_id_ctx

logger = logging.getLogger("app.request")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP-aligned secure response headers (SRS §16)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # API responses carry tenant data; keep them out of shared caches.
        # Signed storage URLs stay cacheable for CDN compatibility.
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v1/storage/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if get_settings().is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates X-Request-ID and emits one structured access log line."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        client_ip_ctx.set(request.client.host if request.client else None)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.info(
            "%s %s -> %s (%sms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        return response
