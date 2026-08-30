import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    loop_enabled: bool = True
    fallback_playlist_id: uuid.UUID | None = None


class PlaylistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    loop_enabled: bool | None = None
    fallback_playlist_id: uuid.UUID | None = None
    clear_fallback: bool = False


class PlaylistItemIn(BaseModel):
    asset_id: uuid.UUID | None = None
    layout_id: uuid.UUID | None = None
    duration_ms: int | None = Field(default=None, gt=0, le=24 * 3600 * 1000)
    transition: dict | None = None
    enabled: bool = True


class ReplaceItemsRequest(BaseModel):
    items: list[PlaylistItemIn] = Field(max_length=500)


class PlaylistItemUpdate(BaseModel):
    duration_ms: int | None = Field(default=None, gt=0, le=24 * 3600 * 1000)
    clear_duration: bool = False
    transition: dict | None = None
    enabled: bool | None = None
    position: int | None = Field(default=None, ge=1)


class PlaylistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    item_type: str
    asset_id: uuid.UUID | None
    layout_id: uuid.UUID | None
    duration_ms: int | None
    transition_json: dict | None
    enabled: bool
    name: str = ""
    asset_type: str | None = None
    thumbnail_url: str | None = None
    ready: bool = True


class PlaylistVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    published_at: datetime


class PlaylistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    loop_enabled: bool
    fallback_playlist_id: uuid.UUID | None
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    item_count: int = 0
    total_duration_ms: int = 0
    current_version_no: int | None = None


class PlaylistDetailOut(PlaylistOut):
    items: list[PlaylistItemOut] = []
    versions: list[PlaylistVersionOut] = []
