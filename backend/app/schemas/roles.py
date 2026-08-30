import uuid

from pydantic import BaseModel, ConfigDict, Field


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permission_codes: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permission_codes: list[str] | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[PermissionOut]
