"""Content studio schemas (P2-M02): widgets and asset collections."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WidgetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    config_schema_json: dict
    defaults_json: dict | None


class WidgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    name: str
    status: str
    fallback_json: dict | None
    created_at: datetime
    versions: list[WidgetVersionOut] = []


class WidgetCreate(BaseModel):
    type: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)
    config_schema_json: dict
    defaults_json: dict | None = None
    fallback_json: dict | None = None


class WidgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    fallback_json: dict | None = None
    clear_fallback: bool = False


class WidgetVersionCreate(BaseModel):
    config_schema_json: dict
    defaults_json: dict | None = None


class CollectionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: uuid.UUID
    position: int


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    items: list[CollectionItemOut] = []


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class CollectionItemsReplace(BaseModel):
    asset_ids: list[uuid.UUID] = Field(max_length=200)


class CollectionToPlaylist(BaseModel):
    playlist_id: uuid.UUID
