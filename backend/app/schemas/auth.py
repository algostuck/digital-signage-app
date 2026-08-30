import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_system: bool


class CurrentUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    active_organization_id: uuid.UUID | None = None
    email: str
    full_name: str
    status: str
    is_superuser: bool
    last_login_at: datetime | None
    roles: list[RoleBrief]
    permissions: list[str] = []


class SwitchTenantRequest(BaseModel):
    organization_id: uuid.UUID
    refresh_token: str


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    is_home: bool
    is_owner: bool
    role_name: str | None


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: CurrentUserOut
