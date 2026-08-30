"""OTA player release / rollout schemas (P2-DEV-004/005)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseCreate(BaseModel):
    version: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
    package_asset_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=1000)


class RolloutStart(BaseModel):
    group_id: uuid.UUID | None = None
    rings: list[int] | None = Field(default=None, max_length=6)
    failure_threshold_pct: int = Field(default=0, ge=0, le=100)


class ReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: str
    package_asset_id: uuid.UUID
    checksum: str
    size_bytes: int
    notes: str | None
    state: str
    created_at: datetime


class PlayerUpdateAck(BaseModel):
    status: str = Field(pattern="^(updating|succeeded|failed)$")
    error: str | None = Field(default=None, max_length=500)
