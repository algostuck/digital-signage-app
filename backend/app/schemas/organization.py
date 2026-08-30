import uuid

from pydantic import BaseModel, ConfigDict, Field


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    status: str
    timezone: str
    locale: str
    branding_json: dict | None
    quotas_json: dict | None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=16)
    branding_json: dict | None = None
