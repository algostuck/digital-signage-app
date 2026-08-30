import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.locations import TagIn, TagOut


class DeviceGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    group_type: str = "static"
    rule_json: dict | None = None
    member_count: int = 0


class DeviceGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    group_type: str = Field(default="static", pattern="^(static|dynamic)$")
    rule_json: dict | None = None


class DeviceGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    rule_json: dict | None = None


class GroupPreviewRequest(BaseModel):
    rule_json: dict


class GroupActionRequest(BaseModel):
    command_type: str = Field(min_length=1, max_length=50)
    payload: dict | None = None


class BulkDeviceUpdate(BaseModel):
    device_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    group_id: uuid.UUID | None = None
    clear_group: bool = False
    location_id: uuid.UUID | None = None
    clear_location: bool = False
    add_tags: list[TagIn] | None = None
    remove_tags: list[TagIn] | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID | None
    type: str
    severity: str
    state: str
    title: str
    opened_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution: str | None
    device_name: str = ""


class DeviceGroupMembersRequest(BaseModel):
    device_ids: list[uuid.UUID]


class DeviceCapabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    capability_code: str
    supported: bool
    value_json: dict | None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID | None
    name: str
    manufacturer: str | None
    model: str | None
    platform: str | None
    os_version: str | None
    player_version: str | None
    serial_no: str
    mac_address: str | None
    ip_address: str | None
    orientation: str | None
    screen_width: int | None
    screen_height: int | None
    timezone: str | None
    status: str
    approved_at: datetime | None
    last_heartbeat_at: datetime | None
    created_at: datetime
    group: DeviceGroupOut | None
    tags: list[TagOut]
    connection_status: str = "n/a"


class DeviceDetailOut(DeviceOut):
    capabilities: list[DeviceCapabilityOut]
    last_heartbeat_json: dict | None
    has_credential: bool = False


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    group_id: uuid.UUID | None = None
    clear_group: bool = False
    timezone: str | None = Field(default=None, max_length=64)
    orientation: str | None = Field(default=None, max_length=20)
    tags: list[TagIn] | None = None


class AssignLocationRequest(BaseModel):
    location_id: uuid.UUID | None = None


class QueueCommandRequest(BaseModel):
    command_type: str = Field(min_length=1, max_length=50)
    payload: dict | None = None


class DeviceCommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    command_type: str
    payload_json: dict | None
    status: str
    created_at: datetime
    sent_at: datetime | None
    acknowledged_at: datetime | None
    result_json: dict | None


class EnrollmentKeyOut(BaseModel):
    enrollment_key: str


# --- player-facing ---


class PlayerRegisterRequest(BaseModel):
    enrollment_key: str = Field(min_length=8, max_length=64)
    serial_no: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    platform: str | None = Field(default=None, max_length=50)
    os_version: str | None = Field(default=None, max_length=50)
    player_version: str | None = Field(default=None, max_length=50)
    mac_address: str | None = Field(default=None, max_length=50)
    screen_width: int | None = Field(default=None, gt=0)
    screen_height: int | None = Field(default=None, gt=0)


class PlayerRegisterOut(BaseModel):
    device_id: uuid.UUID
    status: str
    device_token: str | None = None


class PlayerHeartbeatRequest(BaseModel):
    timestamp: datetime | None = None
    player_version: str | None = None
    os_version: str | None = None
    status: str | None = None
    storage: dict | None = None
    network: dict | None = None
    current: dict | None = None


class PlayerCapabilityIn(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    supported: bool = True
    value: dict | None = None


class PlayerCapabilitiesRequest(BaseModel):
    capabilities: list[PlayerCapabilityIn]


class PlayerCommandAckRequest(BaseModel):
    success: bool = True
    result: dict | None = None
