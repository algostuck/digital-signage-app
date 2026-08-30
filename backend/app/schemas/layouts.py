import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LayoutCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    canvas_width: int = Field(default=1920, gt=0, le=16384)
    canvas_height: int = Field(default=1080, gt=0, le=16384)
    template_id: uuid.UUID | None = None


class LayoutUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    canvas_json: dict | None = None  # designer draft save; validated as LayoutCanvas


class LayoutVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    published_at: datetime


class LayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    zone_count: int = 0
    current_version_no: int | None = None


class LayoutDetailOut(LayoutOut):
    draft_canvas_json: dict
    versions: list[LayoutVersionOut] = []


class TemplateCreate(BaseModel):
    # From an existing layout (Phase-1 path) or from scratch (P2-CNT-001).
    layout_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    canvas_width: int = Field(default=1920, ge=1, le=15360)
    canvas_height: int = Field(default=1080, ge=1, le=15360)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    canvas_json: dict | None = None


class TemplateSubmit(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class TemplateCloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TemplateVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_no: int
    canvas_json: dict
    published_at: datetime


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    layout_id: uuid.UUID | None
    name: str
    description: str | None
    canvas_json: dict
    status: str
    created_at: datetime
    updated_at: datetime
    current_version_no: int | None = None
