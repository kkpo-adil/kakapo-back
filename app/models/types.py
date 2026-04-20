import uuid
import json as _json

from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB


class UUIDType(TypeDecorator):
    """
    Dialect-aware UUID.
    PostgreSQL → native UUID. SQLite (tests) → CHAR(36) TEXT.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONType(TypeDecorator):
    """
    Dialect-aware JSON.
    PostgreSQL → native JSONB. SQLite (tests) → TEXT round-tripped via json.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return None
        return _json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return None
        return _json.loads(value)
