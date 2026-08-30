"""Versioned layout canvas schema (SRS §5.1, §23).

This is the normalized JSON the designer saves, the preview renders, and the
player manifest embeds. Generic zones only — no fixed 1/2/3/6-screen types.
schema_version guards future evolution.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CANVAS_SCHEMA_VERSION = 1

ZONE_CONTENT_TYPES = (
    "placeholder",
    "image",
    "video",
    "playlist",
    "text",
    "ticker",
    "clock",
    "web",
    "widget",
    "qr",
)

MAX_ZONES = 50


class CanvasDef(BaseModel):
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    background: str | None = Field(default="#000000", max_length=50)
    orientation: Literal["landscape", "portrait"] = "landscape"


class ZoneDef(BaseModel):
    key: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(default="Zone", max_length=100)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    z_index: int = Field(default=1, ge=0, le=1000)
    rotation: float = Field(default=0, ge=-360, le=360)
    style: dict = Field(default_factory=dict)
    content_type: str = "placeholder"
    content_config: dict = Field(default_factory=dict)
    # Optional widget instance (P2-CNT-002/003): {widget_id, config, bindings}.
    # Validated against the widget's schema and the approved data-variable
    # catalogue when a template is submitted (studio.validate_canvas_widgets).
    widget: dict | None = None

    @field_validator("content_type")
    @classmethod
    def _known_content_type(cls, value: str) -> str:
        if value not in ZONE_CONTENT_TYPES:
            expected = ", ".join(ZONE_CONTENT_TYPES)
            raise ValueError(f"Unknown zone content type '{value}' (expected one of {expected})")
        return value


class LayoutCanvas(BaseModel):
    schema_version: Literal[1] = CANVAS_SCHEMA_VERSION
    canvas: CanvasDef
    zones: list[ZoneDef] = Field(default_factory=list, max_length=MAX_ZONES)

    @model_validator(mode="after")
    def _unique_zone_keys(self) -> "LayoutCanvas":
        keys = [zone.key for zone in self.zones]
        if len(keys) != len(set(keys)):
            raise ValueError("Zone keys must be unique within a layout")
        return self

    def referenced_asset_ids(self) -> list[str]:
        ids = []
        for zone in self.zones:
            asset_id = zone.content_config.get("asset_id")
            if asset_id:
                ids.append(str(asset_id))
        return ids


def default_canvas(width: int = 1920, height: int = 1080) -> dict:
    return LayoutCanvas(
        canvas=CanvasDef(width=width, height=height),
        zones=[
            ZoneDef(
                key="zone-1",
                name="Main",
                x=0,
                y=0,
                width=width,
                height=height,
                z_index=1,
            )
        ],
    ).model_dump()
