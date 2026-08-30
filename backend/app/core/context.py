"""Request-scoped context shared across layers (logging, auditing, tenancy).

Values are set by middleware / auth dependencies and read anywhere without
threading parameters through every call.
"""

from contextvars import ContextVar
from uuid import UUID

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_ctx: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)
user_id_ctx: ContextVar[UUID | None] = ContextVar("user_id", default=None)
client_ip_ctx: ContextVar[str | None] = ContextVar("client_ip", default=None)
