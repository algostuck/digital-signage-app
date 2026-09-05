import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.core.context import client_ip_ctx, request_id_ctx, tenant_id_ctx, user_id_ctx

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


class RequestContextMiddleware:
    """Assigns/propagates X-Request-ID and emits one structured access log line.

    A pure ASGI middleware on purpose: Starlette's BaseHTTPMiddleware runs
    the downstream app in a separate task, so the tenant and user context
    the auth dependency sets would be invisible here and the access line
    could not say *whose* request it was. In the same task it can.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        client = scope.get("client")
        client_ip_ctx.set(client[0] if client else None)
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw = list(message.get("headers", []))
                raw.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": raw}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            path = scope.get("path", "")
            status = status_holder["status"]
            fields = {
                "method": scope.get("method"),
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
            }
            if tenant_id := tenant_id_ctx.get():
                fields["tenant_id"] = str(tenant_id)
            if user_id := user_id_ctx.get():
                fields["user_id"] = str(user_id)
            logger.info(
                "%s %s -> %s (%sms)",
                scope.get("method"),
                path,
                status,
                duration_ms,
                extra={"extra_fields": fields},
            )
            request_id_ctx.reset(token)
