"""Dialect-portable column types.

Every environment — dev, test and production — runs PostgreSQL (UUID,
JSONB). The decorators keep the models dialect-portable as defensive
engineering, but no non-PostgreSQL engine is part of the toolchain.
"""

import uuid
from datetime import UTC

from sqlalchemy import CHAR, JSON, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """UUID stored natively on PostgreSQL, CHAR(36) elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class UTCDateTime(TypeDecorator):
    """timestamptz that always yields timezone-aware UTC datetimes.

    PostgreSQL returns aware values natively; SQLite returns naive ones,
    which would serialize without a UTC marker and be misparsed by clients.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class JSONType(TypeDecorator):
    """JSONB on PostgreSQL, generic JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
