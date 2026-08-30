import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import RoleBrief


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    role_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role_ids: list[uuid.UUID] | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    roles: list[RoleBrief]
