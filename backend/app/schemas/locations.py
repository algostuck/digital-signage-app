import uuid

from pydantic import BaseModel, ConfigDict, Field


class LocationTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str


class LocationTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: str


class TagIn(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=200)


class SetTagsRequest(BaseModel):
    tags: list[TagIn]


class LocationBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    type_id: uuid.UUID | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    metadata_json: dict | None = None


class LocationCreate(LocationBase):
    parent_id: uuid.UUID | None = None


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    type_id: uuid.UUID | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    metadata_json: dict | None = None


class LocationMoveRequest(BaseModel):
    new_parent_id: uuid.UUID | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    code: str | None
    path: str
    depth: int
    address: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    status: str
    metadata_json: dict | None
    type: LocationTypeOut | None
    tags: list[TagOut]


class LocationDetailOut(LocationOut):
    effective_timezone: str
    children_count: int
    descendants_count: int


class LocationTreeNode(BaseModel):
    node: LocationOut
    children: list["LocationTreeNode"]


LocationTreeNode.model_rebuild()
