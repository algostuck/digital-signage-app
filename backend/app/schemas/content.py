import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.locations import TagIn, TagOut


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    status: str


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None


class FolderUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class UploadSessionCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=200)
    size_bytes: int = Field(gt=0)
    folder_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None  # set -> new version of an existing asset
    name: str | None = Field(default=None, max_length=255)


class UploadSessionOut(BaseModel):
    upload_session_id: uuid.UUID
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_at: datetime
    asset_id: uuid.UUID
    version_no: int


class AssetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum: str | None
    width: int | None
    height: int | None
    duration_ms: int | None
    processing_status: str
    processing_error: str | None
    created_at: datetime


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folder_id: uuid.UUID | None
    type: str
    name: str
    description: str | None
    status: str
    checksum: str | None
    created_at: datetime
    updated_at: datetime
    tags: list[TagOut]
    current_version: AssetVersionOut | None = None
    thumbnail_url: str | None = None


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    folder_id: uuid.UUID | None = None
    clear_folder: bool = False
    tags: list[TagIn] | None = None


class DownloadUrlOut(BaseModel):
    url: str
    expires_in: int
