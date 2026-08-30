"""Current-tenant organization settings (FR-ORG-001/002/003)."""

import logging
import uuid
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.models import Organization

logger = logging.getLogger("app.organization")


@lru_cache(maxsize=512)
def is_valid_timezone(tz: str) -> bool:
    try:
        ZoneInfo(tz)
        return True
    except Exception:
        return False


def validate_timezone(tz: str) -> None:
    if not is_valid_timezone(tz):
        raise ValidationAppError(f"Unknown IANA timezone: {tz}", field="timezone")


# --- per-tenant monitoring thresholds (P2-MON-002) ---


def _default_thresholds() -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "warning_after_seconds": settings.device_warning_after_seconds,
        "offline_after_seconds": settings.device_offline_after_seconds,
        "storage_alert_percent": 90,
        "min_player_version": None,
    }


async def get_monitoring_thresholds(
    db: AsyncSession, organization_id: uuid.UUID
) -> dict:
    """Platform defaults overlaid with the tenant's overrides."""
    org = await get_organization(db, organization_id)
    thresholds = _default_thresholds()
    thresholds.update((org.settings_json or {}).get("monitoring") or {})
    return thresholds


async def update_monitoring_thresholds(
    db: AsyncSession,
    organization_id: uuid.UUID,
    values: dict,
    *,
    user_id: uuid.UUID | None = None,
) -> dict:
    allowed = set(_default_thresholds())
    unknown = set(values) - allowed
    if unknown:
        raise ValidationAppError(f"Unknown threshold keys: {sorted(unknown)}")
    for key in ("warning_after_seconds", "offline_after_seconds"):
        if key in values and values[key] is not None:
            if not isinstance(values[key], int) or not 30 <= values[key] <= 86400:
                raise ValidationAppError(f"{key} must be 30..86400 seconds", field=key)
    if values.get("storage_alert_percent") is not None:
        pct = values["storage_alert_percent"]
        if not isinstance(pct, int) or not 50 <= pct <= 100:
            raise ValidationAppError(
                "storage_alert_percent must be 50..100", field="storage_alert_percent"
            )
    if values.get("min_player_version") is not None and (
        not isinstance(values["min_player_version"], str)
        or len(values["min_player_version"]) > 50
    ):
        raise ValidationAppError(
            "min_player_version must be a short version string", field="min_player_version"
        )
    merged = {**_default_thresholds(), **values}
    if merged["warning_after_seconds"] >= merged["offline_after_seconds"]:
        raise ValidationAppError(
            "warning_after_seconds must be below offline_after_seconds",
            field="warning_after_seconds",
        )

    org = await get_organization(db, organization_id)
    settings_json = dict(org.settings_json or {})
    settings_json["monitoring"] = {k: v for k, v in values.items() if v is not None}
    org.settings_json = settings_json
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="MONITORING_THRESHOLDS_UPDATED",
        entity_type="organization",
        entity_id=organization_id,
        after=settings_json["monitoring"],
        user_id=user_id,
    )
    logger.info("Monitoring thresholds updated for org %s", organization_id)
    return await get_monitoring_thresholds(db, organization_id)


async def get_organization(db: AsyncSession, organization_id: uuid.UUID) -> Organization:
    org = await db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Organization not found")
    return org


async def update_organization(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str | None = None,
    timezone: str | None = None,
    locale: str | None = None,
    branding_json: dict | None = None,
) -> Organization:
    org = await get_organization(db, organization_id)
    if name is not None:
        org.name = name
    if timezone is not None:
        validate_timezone(timezone)
        org.timezone = timezone
    if locale is not None:
        org.locale = locale
    if branding_json is not None:
        org.branding_json = branding_json
    await db.flush()
    logger.info("Organization %s updated", org.id)
    return org
