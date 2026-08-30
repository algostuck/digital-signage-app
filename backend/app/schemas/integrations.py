"""Integration schemas (P2-M10). Secrets appear only in create/rotate
responses — never in list/detail output."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=500)
    event_types_json: list[str] = Field(min_length=1, max_length=20)


class WebhookUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=500)
    event_types_json: list[str] | None = Field(default=None, max_length=20)
    active: bool | None = None


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    description: str | None
    event_types_json: list[str]
    active: bool
    created_at: dt.datetime


class WebhookDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    event_id: uuid.UUID
    state: str
    attempt_no: int
    response_code: int | None
    last_error: str | None
    next_attempt_at: dt.datetime | None
    delivered_at: dt.datetime | None
    created_at: dt.datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(min_length=1, max_length=50)
    expires_at: dt.datetime | None = None


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    scopes_json: list[str]
    expires_at: dt.datetime | None
    revoked_at: dt.datetime | None
    last_used_at: dt.datetime | None
    created_at: dt.datetime
