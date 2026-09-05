import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    priority: int = Field(default=50, ge=1, le=100)
    playlist_id: uuid.UUID | None = None
    layout_id: uuid.UUID | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    priority: int | None = Field(default=None, ge=1, le=100)
    playlist_id: uuid.UUID | None = None
    layout_id: uuid.UUID | None = None
    clear_playlist: bool = False
    clear_layout: bool = False


class ScheduleCreate(BaseModel):
    campaign_id: uuid.UUID
    name: str | None = Field(default=None, max_length=200)
    kind: str = Field(default="play", pattern="^(play|blackout)$")
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    days_of_week: list[int] | None = None
    recurrence_json: dict | None = None
    exception_dates_json: list[str] | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=50, ge=1, le=100)


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, pattern="^(play|blackout)$")
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    days_of_week: list[int] | None = None
    recurrence_json: dict | None = None
    exception_dates_json: list[str] | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    priority: int | None = Field(default=None, ge=1, le=100)


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str | None
    kind: str
    start_date: dt.date | None
    end_date: dt.date | None
    start_time: dt.time | None
    end_time: dt.time | None
    days_of_week: list[int] | None
    recurrence_json: dict | None
    exception_dates_json: list[str] | None
    timezone: str | None
    priority: int
    created_at: dt.datetime
    expired: bool = False


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    priority: int
    playlist_id: uuid.UUID | None
    layout_id: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    schedule_count: int = 0


class CampaignDetailOut(CampaignOut):
    schedules: list[ScheduleOut] = []


class VariantTargetIn(BaseModel):
    target_type: str = Field(pattern="^(location|device|group|tag)$")
    target_id: uuid.UUID
    include_descendants: bool = True


class VariantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    layout_id: uuid.UUID | None = None
    playlist_id: uuid.UUID | None = None
    priority: int = Field(default=50, ge=1, le=100)
    targets: list[VariantTargetIn] = Field(min_length=1, max_length=50)


class VariantTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_type: str
    target_id: uuid.UUID
    include_descendants: bool


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    layout_id: uuid.UUID | None
    playlist_id: uuid.UUID | None
    priority: int
    targets: list[VariantTargetOut] = []


class ConflictCheckRequest(BaseModel):
    """Dry-run: check a proposed schedule against everything already on the
    calendar before saving it (P2-SCH-004)."""

    campaign_id: uuid.UUID
    kind: str = Field(default="play", pattern="^(play|blackout)$")
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    days_of_week: list[int] | None = None
    recurrence_json: dict | None = None
    exception_dates_json: list[str] | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=50, ge=1, le=100)
    range_start: dt.date | None = None
    range_end: dt.date | None = None
    # Editing an existing window: leave its current definition out of the
    # comparison so it does not "conflict" with itself.
    schedule_id: uuid.UUID | None = None


class TargetIn(BaseModel):
    target_type: str = Field(pattern="^(location|device|group|tag)$")
    target_id: uuid.UUID
    include_descendants: bool = True
    is_exclusion: bool = False


class SetTargetsRequest(BaseModel):
    targets: list[TargetIn] = Field(max_length=200)


class TargetsPreviewRequest(BaseModel):
    targets: list[TargetIn] = Field(min_length=1, max_length=200)


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    include_descendants: bool
    is_exclusion: bool


class EffectiveDeviceOut(BaseModel):
    id: uuid.UUID
    name: str
    serial_no: str
    platform: str | None


class DeploymentDeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: uuid.UUID
    status: str
    attempts: int
    last_error: str | None
    acknowledged_at: dt.datetime | None
    device_name: str = ""


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    version: int
    status: str
    error: str | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    created_at: dt.datetime
    campaign_name: str = ""
    total_devices: int = 0
    acknowledged: int = 0
    failed: int = 0
    pending: int = 0


class PlayerDeploymentAck(BaseModel):
    success: bool = True
    error: str | None = Field(default=None, max_length=1000)


class CalendarEventOut(BaseModel):
    schedule_id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_name: str
    schedule_name: str | None
    date: dt.date
    start_minute: int
    end_minute: int
    priority: int
    campaign_priority: int
    timezone: str | None
    kind: str = "play"
    overnight: bool
    conflict: bool
    # Schedule workspace contract (docs/SCHEDULE_UX_AUDIT.md §10.2)
    campaign_status: str | None = None
    recurrence_type: str = "daily"
    recurrence_text: str = ""
    days_of_week: list[int] | None = None
    expired: bool = False
    live: bool = False
    screens: int = 0
    locations: int = 0
    conflict_ids: list[str] = Field(default_factory=list)


class ConflictCampaignOut(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    campaign_status: str | None
    campaign_priority: int
    schedule_id: uuid.UUID
    schedule_name: str | None
    schedule_priority: int
    kind: str


class ConflictDatesOut(BaseModel):
    first: dt.date
    last: dt.date
    count: int


class ConflictScreensOut(BaseModel):
    count: int
    names: list[str]


class ConflictOut(BaseModel):
    """One actionable scheduling conflict, grouped across the range
    (docs/SCHEDULE_UX_AUDIT.md §10.3)."""

    id: str
    severity: str = Field(pattern="^(high|medium|low)$")
    reason: str
    message: str
    window: list[int]
    campaigns: list[ConflictCampaignOut]
    winner_campaign_id: uuid.UUID | None
    screens_affected: ConflictScreensOut
    dates: ConflictDatesOut
    suggestions: list[str]


class CalendarSummaryOut(BaseModel):
    campaigns: int
    screens: int
    play_windows: int
    blackout_windows: int
    conflicts_actionable: int
    conflicts_high: int
    conflicts_medium: int
    conflicts_low: int
    conflicts_total_estate: int


class CalendarNowOut(BaseModel):
    at: dt.datetime
    date: dt.date
    minute: int


class CalendarOut(BaseModel):
    range_start: dt.date
    range_end: dt.date
    timezone: str = "UTC"
    now: CalendarNowOut | None = None
    events: list[CalendarEventOut]
    conflicts: list[ConflictOut] = Field(default_factory=list)
    summary: CalendarSummaryOut | None = None
    conflict_count: int
