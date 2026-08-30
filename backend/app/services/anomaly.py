"""Fleet intelligence engine (P3-M07, slice 3D-3) — deterministic first.

Signals are explainable statistics over telemetry the platform already
records (heartbeats, playback events, device events). Every anomaly's
`evidence_json` names the exact numbers behind its score; recommendations
are advisory text and remediation executes only whitelisted, non-destructive
device commands with a full action trail (P3-OPS-003). A model-based scorer
can plug in behind detect() later — the interface won't change.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.models import (
    Anomaly,
    AnomalyAction,
    AnomalyRule,
    Device,
    DeviceEvent,
    DeviceHeartbeat,
    PlaybackEvent,
)
from app.models.anomaly import AnomalySignal, AnomalyState
from app.models.device import DeviceStatus

logger = logging.getLogger("app.anomaly")

WHITELISTED_REMEDIATIONS = {
    "restart": "Restart the player application",
    "clear_cache": "Clear the player's local cache",
    "refresh_content": "Force a manifest re-sync",
}

THRESHOLD_DEFAULTS: dict[str, dict] = {
    AnomalySignal.HEARTBEAT_GAPS.value: {"gap_minutes": 10, "max_gaps": 3},
    AnomalySignal.PLAYBACK_FAILURES.value: {"min_events": 10, "max_failure_pct": 20},
    AnomalySignal.ERROR_EVENTS.value: {"max_count": 5},
}

RECOMMENDATIONS = {
    AnomalySignal.HEARTBEAT_GAPS.value:
        "Connectivity is flapping. Check network/power at the site; a player "
        "restart often clears stuck network stacks.",
    AnomalySignal.PLAYBACK_FAILURES.value:
        "Playback is failing repeatedly. Verify the assigned content decodes "
        "on this hardware; clearing the cache forces a clean re-download.",
    AnomalySignal.ERROR_EVENTS.value:
        "The device is logging errors above baseline. Review the event "
        "timeline; a restart is the safe first step.",
}


def _validate_rule(signal_type: str, threshold: dict, window_hours: int) -> dict:
    if signal_type not in {s.value for s in AnomalySignal}:
        raise ValidationAppError(
            f"signal_type must be one of {[s.value for s in AnomalySignal]}",
            field="signal_type",
        )
    if not 1 <= window_hours <= 168:
        raise ValidationAppError("window_hours must be 1..168", field="window_hours")
    merged = {**THRESHOLD_DEFAULTS[signal_type], **(threshold or {})}
    unknown = set(merged) - set(THRESHOLD_DEFAULTS[signal_type])
    if unknown:
        raise ValidationAppError(f"Unknown threshold keys: {sorted(unknown)}")
    for key, value in merged.items():
        if not isinstance(value, int | float) or value <= 0:
            raise ValidationAppError(f"threshold.{key} must be a positive number")
    return merged


# --- rules CRUD ---


async def list_rules(db: AsyncSession, organization_id: uuid.UUID) -> list[AnomalyRule]:
    rows = await db.execute(
        select(AnomalyRule)
        .where(AnomalyRule.organization_id == organization_id)
        .order_by(AnomalyRule.name)
    )
    return list(rows.scalars().all())


async def create_rule(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    signal_type: str,
    threshold: dict | None = None,
    window_hours: int = 24,
    severity: str = "warning",
    user_id: uuid.UUID | None = None,
) -> AnomalyRule:
    from app.services import entitlements

    await entitlements.require_feature(db, organization_id, "fleet_ai")
    exists = (
        await db.execute(
            select(AnomalyRule).where(
                AnomalyRule.organization_id == organization_id, AnomalyRule.name == name
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A rule with this name already exists", field="name")
    rule = AnomalyRule(
        organization_id=organization_id,
        name=name,
        signal_type=signal_type,
        threshold_json=_validate_rule(signal_type, threshold or {}, window_hours),
        window_hours=window_hours,
        severity=severity if severity in ("info", "warning", "critical") else "warning",
    )
    db.add(rule)
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="ANOMALY_RULE_CREATED",
        entity_type="anomaly_rule", entity_id=rule.id,
        after={"name": name, "signal_type": signal_type}, user_id=user_id,
    )
    return rule


async def update_rule(
    db: AsyncSession, organization_id: uuid.UUID, rule_id: uuid.UUID, **changes
) -> AnomalyRule:
    rule = (
        await db.execute(
            select(AnomalyRule).where(
                AnomalyRule.organization_id == organization_id, AnomalyRule.id == rule_id
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Anomaly rule not found")
    if changes.get("threshold") is not None or changes.get("window_hours") is not None:
        rule.threshold_json = _validate_rule(
            rule.signal_type,
            changes.get("threshold") or rule.threshold_json,
            changes.get("window_hours") or rule.window_hours,
        )
    for field in ("name", "window_hours", "severity", "active"):
        if field in changes and changes[field] is not None:
            setattr(rule, field, changes[field])
    await db.flush()
    return rule


async def delete_rule(
    db: AsyncSession, organization_id: uuid.UUID, rule_id: uuid.UUID
) -> None:
    rule = (
        await db.execute(
            select(AnomalyRule).where(
                AnomalyRule.organization_id == organization_id, AnomalyRule.id == rule_id
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Anomaly rule not found")
    await db.delete(rule)
    await db.flush()


# --- signal computation (pure statistics, evidence included) ---


async def _signal_value(
    db: AsyncSession, device: Device, rule: AnomalyRule, since: datetime
) -> tuple[float, float, dict]:
    """Returns (value, threshold_reference, evidence)."""
    threshold = rule.threshold_json
    if rule.signal_type == AnomalySignal.HEARTBEAT_GAPS.value:
        beats = (
            await db.execute(
                select(DeviceHeartbeat.observed_at)
                .where(
                    DeviceHeartbeat.device_id == device.id,
                    DeviceHeartbeat.observed_at >= since,
                )
                .order_by(DeviceHeartbeat.observed_at)
            )
        ).scalars().all()
        gap_limit = timedelta(minutes=threshold["gap_minutes"])
        gaps = []
        for previous, current in zip(beats, beats[1:], strict=False):
            previous = previous if previous.tzinfo else previous.replace(tzinfo=UTC)
            current = current if current.tzinfo else current.replace(tzinfo=UTC)
            if current - previous > gap_limit:
                gaps.append(
                    {"from": previous.isoformat(), "to": current.isoformat(),
                     "minutes": round((current - previous).total_seconds() / 60, 1)}
                )
        return (
            float(len(gaps)),
            float(threshold["max_gaps"]),
            {"heartbeats": len(beats), "gaps": gaps[:10],
             "gap_minutes_threshold": threshold["gap_minutes"]},
        )
    if rule.signal_type == AnomalySignal.PLAYBACK_FAILURES.value:
        total = (
            await db.execute(
                select(func.count()).where(
                    PlaybackEvent.device_id == device.id,
                    PlaybackEvent.started_at >= since,
                )
            )
        ).scalar_one()
        failed = (
            await db.execute(
                select(func.count()).where(
                    PlaybackEvent.device_id == device.id,
                    PlaybackEvent.started_at >= since,
                    PlaybackEvent.result != "completed",
                )
            )
        ).scalar_one()
        if total < threshold["min_events"]:
            return 0.0, float(threshold["max_failure_pct"]), {
                "total": total, "failed": failed,
                "note": f"below min_events={threshold['min_events']}",
            }
        pct = 100 * failed / total
        return (
            round(pct, 1),
            float(threshold["max_failure_pct"]),
            {"total": total, "failed": failed, "failure_pct": round(pct, 1)},
        )
    # error_events
    count = (
        await db.execute(
            select(func.count()).where(
                DeviceEvent.device_id == device.id,
                DeviceEvent.event_at >= since,
                DeviceEvent.type.in_(("error", "crash", "exception")),
            )
        )
    ).scalar_one()
    return float(count), float(threshold["max_count"]), {"error_events": count}


async def detect(db: AsyncSession, *, limit_devices: int = 500) -> dict:
    """Beat sweep: score every active device against every active rule.
    Opens one anomaly per (device, rule) episode; resolves open ones whose
    signal has cleared (outcome recorded — self-healing evidence)."""
    rules = (
        await db.execute(select(AnomalyRule).where(AnomalyRule.active.is_(True)))
    ).scalars().all()
    opened = resolved = 0
    now = datetime.now(UTC)
    for rule in rules:
        devices = (
            await db.execute(
                select(Device)
                .where(
                    Device.organization_id == rule.organization_id,
                    Device.status == DeviceStatus.ACTIVE.value,
                )
                .limit(limit_devices)
            )
        ).scalars().all()
        since = now - timedelta(hours=rule.window_hours)
        for device in devices:
            value, reference, evidence = await _signal_value(db, device, rule, since)
            score = round(value / reference, 2) if reference else 0.0
            existing = (
                await db.execute(
                    select(Anomaly).where(
                        Anomaly.device_id == device.id,
                        Anomaly.rule_id == rule.id,
                        Anomaly.state.in_(
                            [AnomalyState.OPEN.value, AnomalyState.ACKNOWLEDGED.value]
                        ),
                    )
                )
            ).scalar_one_or_none()
            exceeded = value > reference
            if exceeded and existing is None:
                db.add(
                    Anomaly(
                        organization_id=rule.organization_id,
                        device_id=device.id,
                        rule_id=rule.id,
                        score=score,
                        evidence_json={
                            "signal": rule.signal_type,
                            "value": value,
                            "threshold": reference,
                            "window_hours": rule.window_hours,
                            **evidence,
                        },
                        recommendation=RECOMMENDATIONS.get(rule.signal_type),
                    )
                )
                opened += 1
            elif not exceeded and existing is not None:
                existing.state = AnomalyState.RESOLVED.value
                existing.resolved_at = now
                db.add(
                    AnomalyAction(
                        anomaly_id=existing.id,
                        action="auto_resolve",
                        outcome="signal cleared on re-scan",
                    )
                )
                resolved += 1
            elif exceeded and existing is not None:
                existing.score = score  # keep the score honest on re-scan
    await db.flush()
    return {"opened": opened, "resolved": resolved, "rules": len(rules)}


# --- anomalies: list / ack / remediate ---


async def list_anomalies(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    state: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Anomaly], int]:
    query = select(Anomaly).where(Anomaly.organization_id == organization_id)
    if state:
        query = query.where(Anomaly.state == state)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(Anomaly.opened_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def _get_anomaly(
    db: AsyncSession, organization_id: uuid.UUID, anomaly_id: uuid.UUID
) -> Anomaly:
    anomaly = (
        await db.execute(
            select(Anomaly).where(
                Anomaly.organization_id == organization_id, Anomaly.id == anomaly_id
            )
        )
    ).scalar_one_or_none()
    if anomaly is None:
        raise NotFoundError("Anomaly not found")
    return anomaly


async def acknowledge(
    db: AsyncSession, organization_id: uuid.UUID, anomaly_id: uuid.UUID,
    *, user_id: uuid.UUID | None,
) -> Anomaly:
    anomaly = await _get_anomaly(db, organization_id, anomaly_id)
    if anomaly.state != AnomalyState.OPEN.value:
        raise BusinessRuleError("Only open anomalies can be acknowledged")
    anomaly.state = AnomalyState.ACKNOWLEDGED.value
    db.add(AnomalyAction(anomaly_id=anomaly.id, actor_id=user_id, action="acknowledge"))
    await db.flush()
    return anomaly


async def remediate(
    db: AsyncSession, organization_id: uuid.UUID, anomaly_id: uuid.UUID,
    *, action: str, user_id: uuid.UUID | None,
) -> dict:
    """Whitelisted commands only, queued through the standard device command
    channel — never executed autonomously, always trailed."""
    if action not in WHITELISTED_REMEDIATIONS:
        raise ValidationAppError(
            f"action must be one of {sorted(WHITELISTED_REMEDIATIONS)}", field="action"
        )
    anomaly = await _get_anomaly(db, organization_id, anomaly_id)
    from app.services import devices as devices_service

    command = await devices_service.queue_command(
        db, organization_id, anomaly.device_id,
        command_type=action, payload={"source": "fleet_intelligence",
                                      "anomaly_id": str(anomaly.id)},
    )
    db.add(
        AnomalyAction(
            anomaly_id=anomaly.id,
            actor_id=user_id,
            action=f"remediate:{action}",
            outcome=f"command {command.id} queued",
        )
    )
    await db.flush()

    from app.services import audit

    await audit.record(
        db, organization_id, action="ANOMALY_REMEDIATION",
        entity_type="anomaly", entity_id=anomaly.id,
        after={"remediation": action, "command_id": str(command.id)}, user_id=user_id,
    )
    logger.info("Anomaly %s remediation %s queued (%s)", anomaly.id, action, command.id)
    return {"anomaly_id": str(anomaly.id), "command_id": str(command.id), "action": action}


async def actions_for(
    db: AsyncSession, organization_id: uuid.UUID, anomaly_id: uuid.UUID
) -> list[AnomalyAction]:
    await _get_anomaly(db, organization_id, anomaly_id)
    rows = await db.execute(
        select(AnomalyAction)
        .where(AnomalyAction.anomaly_id == anomaly_id)
        .order_by(AnomalyAction.executed_at)
    )
    return list(rows.scalars().all())
