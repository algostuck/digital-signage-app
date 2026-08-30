"""Notification rule schemas (P2-M08)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RuleChannel(BaseModel):
    channel: str = Field(pattern="^(in_app|email|webhook)$")
    recipient: str | None = Field(default=None, max_length=500)


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    event_type: str = Field(min_length=1, max_length=60)
    condition_json: dict | None = None
    channels_json: list[RuleChannel] = Field(min_length=1, max_length=10)
    escalation_minutes: int | None = Field(default=None, ge=1, le=1440)


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    event_type: str | None = Field(default=None, min_length=1, max_length=60)
    condition_json: dict | None = None
    channels_json: list[RuleChannel] | None = Field(default=None, max_length=10)
    escalation_minutes: int | None = Field(default=None, ge=1, le=1440)
    active: bool | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_type: str
    condition_json: dict | None
    channels_json: list
    escalation_minutes: int | None
    active: bool
    created_at: dt.datetime


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    notification_id: uuid.UUID
    channel: str
    recipient: str
    state: str
    attempts: int
    last_error: str | None
    delivered_at: dt.datetime | None
    created_at: dt.datetime
    notification_title: str = ""
    notification_type: str = ""
