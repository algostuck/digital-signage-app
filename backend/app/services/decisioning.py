"""Decisioning engine (P3-M03, slice 3B-2).

Sits BETWEEN the 1H schedule resolver and the manifest: given the device's
schedule-eligible candidates, ordered rules may pin, boost or exclude
campaigns — deterministically, with every applied rule recorded as a
reason (P3-DEC-002). Degradation ladder (never a blank screen):

    active rules match → decided winner (logged)
    no rules / no match / engine error → 1H scheduler result
    nothing scheduled → 1G fallback chain (manifest, unchanged)

Guardrails (P3-DEC-004): schedule windows are never overridden (a pinned
campaign must still be schedule-eligible), mandatory campaigns cannot be
excluded, and max_switches_per_hour caps how often decisioning may flip a
device away from the scheduler's own choice.
"""

import datetime as dt
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models import (
    Campaign,
    DecisionLog,
    DecisionPolicy,
    DecisionRule,
    Device,
    Location,
)

logger = logging.getLogger("app.decisioning")

CONDITION_KEYS = {"platform", "manufacturer", "location_id", "tag", "time", "data"}
ACTION_KEYS = {"pin", "boost", "exclude"}
DEFAULT_GUARDRAILS = {
    "mandatory_campaign_ids": [],
    "max_switches_per_hour": 12,
}


# --- validation ---


def _validate_rule(conditions: dict, actions: dict) -> None:
    unknown = set(conditions) - CONDITION_KEYS
    if unknown:
        raise ValidationAppError(f"Unknown condition keys: {sorted(unknown)}")
    time_rule = conditions.get("time")
    if time_rule is not None:
        if not isinstance(time_rule, dict) or not {"start", "end"} <= set(time_rule):
            raise ValidationAppError('time condition needs {"start","end"[,"days"]}')
        for field in ("start", "end"):
            try:
                dt.time.fromisoformat(time_rule[field])
            except (TypeError, ValueError) as exc:
                raise ValidationAppError(f"time.{field} must be HH:MM") from exc
    tag_rule = conditions.get("tag")
    if tag_rule is not None and (
        not isinstance(tag_rule, dict) or "key" not in tag_rule
    ):
        raise ValidationAppError('tag condition needs {"key"[,"value"]}')
    data_rule = conditions.get("data")
    if data_rule is not None:
        if not isinstance(data_rule, dict) or not {"source_id", "path", "op", "value"} <= set(
            data_rule
        ):
            raise ValidationAppError('data condition needs {"source_id","path","op","value"}')
        if data_rule["op"] not in ("eq", "ne", "gt", "lt", "contains"):
            raise ValidationAppError("data.op must be eq/ne/gt/lt/contains")

    action_keys = set(actions) & ACTION_KEYS
    if len(action_keys) != 1:
        raise ValidationAppError("actions must contain exactly one of pin/boost/exclude")
    amount = actions.get("amount")
    if amount is not None and (not isinstance(amount, int) or not 1 <= amount <= 1000):
        raise ValidationAppError("actions.amount must be 1..1000")


def _validate_guardrails(guardrails: dict) -> dict:
    merged = {**DEFAULT_GUARDRAILS, **guardrails}
    unknown = set(merged) - set(DEFAULT_GUARDRAILS)
    if unknown:
        raise ValidationAppError(f"Unknown guardrail keys: {sorted(unknown)}")
    if not isinstance(merged["mandatory_campaign_ids"], list):
        raise ValidationAppError("mandatory_campaign_ids must be a list")
    cap = merged["max_switches_per_hour"]
    if not isinstance(cap, int) or not 0 <= cap <= 1000:
        raise ValidationAppError("max_switches_per_hour must be 0..1000")
    return merged


# --- policy CRUD ---


async def list_policies(db: AsyncSession, organization_id: uuid.UUID) -> list[DecisionPolicy]:
    rows = await db.execute(
        select(DecisionPolicy)
        .where(DecisionPolicy.organization_id == organization_id)
        .order_by(DecisionPolicy.created_at)
    )
    return list(rows.scalars().all())


async def get_policy(
    db: AsyncSession, organization_id: uuid.UUID, policy_id: uuid.UUID
) -> DecisionPolicy:
    policy = (
        await db.execute(
            select(DecisionPolicy).where(
                DecisionPolicy.organization_id == organization_id,
                DecisionPolicy.id == policy_id,
            )
        )
    ).scalar_one_or_none()
    if policy is None:
        raise NotFoundError("Decision policy not found")
    return policy


async def create_policy(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str,
    guardrails: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> DecisionPolicy:
    exists = (
        await db.execute(
            select(DecisionPolicy).where(
                DecisionPolicy.organization_id == organization_id,
                DecisionPolicy.name == name,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A decision policy with this name already exists", field="name")
    policy = DecisionPolicy(
        organization_id=organization_id,
        name=name,
        guardrails_json=_validate_guardrails(guardrails or {}),
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy, ["rules"])

    from app.services import audit

    await audit.record(
        db, organization_id, action="DECISION_POLICY_CREATED",
        entity_type="decision_policy", entity_id=policy.id,
        after={"name": name}, user_id=user_id,
    )
    return policy


async def update_policy(
    db: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    *,
    name: str | None = None,
    guardrails: dict | None = None,
    active: bool | None = None,
) -> DecisionPolicy:
    policy = await get_policy(db, organization_id, policy_id)
    if name is not None:
        policy.name = name
    if guardrails is not None:
        policy.guardrails_json = _validate_guardrails(guardrails)
    if active is not None:
        policy.active = active
    await db.flush()
    return policy


async def delete_policy(
    db: AsyncSession, organization_id: uuid.UUID, policy_id: uuid.UUID
) -> None:
    policy = await get_policy(db, organization_id, policy_id)
    await db.delete(policy)
    await db.flush()


async def set_rules(
    db: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    rules: list[dict],
) -> DecisionPolicy:
    """Replace-set (the platform's list-edit idiom)."""
    policy = await get_policy(db, organization_id, policy_id)
    if len(rules) > 50:
        raise ValidationAppError("At most 50 rules per policy")
    for rule in rules:
        _validate_rule(rule.get("conditions") or {}, rule.get("actions") or {})
    policy.rules.clear()
    await db.flush()
    policy.rules.extend(
        DecisionRule(
            policy_id=policy.id,
            priority=rule.get("priority", 100),
            conditions_json=rule.get("conditions") or {},
            actions_json=rule.get("actions") or {},
        )
        for rule in rules
    )
    await db.flush()
    await db.refresh(policy, ["rules"])
    return policy


# --- evaluation ---


async def _conditions_match(
    db: AsyncSession,
    device: Device,
    conditions: dict,
    now_local: datetime,
) -> tuple[bool, list[str]]:
    matched: list[str] = []
    platform = conditions.get("platform")
    if platform is not None:
        if (device.platform or "").lower() != str(platform).lower():
            return False, []
        matched.append(f"platform={platform}")
    manufacturer = conditions.get("manufacturer")
    if manufacturer is not None:
        if (device.manufacturer or "").lower() != str(manufacturer).lower():
            return False, []
        matched.append(f"manufacturer={manufacturer}")
    location_id = conditions.get("location_id")
    if location_id is not None:
        if device.location_id is None:
            return False, []
        location = await db.get(Location, device.location_id)
        if location is None or str(location_id) not in location.path:
            return False, []
        matched.append(f"location subtree {location_id}")
    tag_rule = conditions.get("tag")
    if tag_rule is not None:
        tags = {t.key: t.value for t in device.tags}
        key, value = tag_rule["key"], tag_rule.get("value")
        if key not in tags or (value is not None and tags[key] != value):
            return False, []
        matched.append(f"tag {key}={tags[key]}")
    time_rule = conditions.get("time")
    if time_rule is not None:
        start = dt.time.fromisoformat(time_rule["start"])
        end = dt.time.fromisoformat(time_rule["end"])
        current = now_local.time()
        days = time_rule.get("days")
        in_day = days is None or now_local.isoweekday() in days
        in_window = (
            start <= current <= end if start <= end else current >= start or current <= end
        )
        if not (in_day and in_window):
            return False, []
        matched.append(f"time {time_rule['start']}-{time_rule['end']}")
    data_rule = conditions.get("data")
    if data_rule is not None:
        from app.services.data_sources import _pick, latest_valid_snapshot

        try:
            snapshot = await latest_valid_snapshot(db, uuid.UUID(str(data_rule["source_id"])))
        except ValueError:
            return False, []
        if snapshot is None:
            return False, []  # no external context -> condition cannot hold
        actual = _pick(snapshot.payload_json, data_rule["path"])
        expected, op = data_rule["value"], data_rule["op"]
        try:
            ok = {
                "eq": lambda: actual == expected,
                "ne": lambda: actual != expected,
                "gt": lambda: float(actual) > float(expected),
                "lt": lambda: float(actual) < float(expected),
                "contains": lambda: str(expected).lower() in str(actual).lower(),
            }[op]()
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return False, []
        matched.append(f"data {data_rule['path']} {op} {expected} (actual={actual})")
    return True, matched


async def _switches_last_hour(
    db: AsyncSession, device_id: uuid.UUID
) -> int:
    return (
        await db.execute(
            select(func.count()).where(
                DecisionLog.device_id == device_id,
                DecisionLog.decided_at >= datetime.now(UTC) - timedelta(hours=1),
            )
        )
    ).scalar_one()


async def decide(
    db: AsyncSession,
    device: Device,
    candidates: list[Campaign],
    scheduler_winner: Campaign | None,
    *,
    now_local: datetime,
    log: bool = True,
) -> tuple[Campaign | None, list[dict]]:
    """Returns (winner, reasons). With no active rules (or on any engine
    error) the scheduler's own choice passes through untouched."""
    policies = (
        await db.execute(
            select(DecisionPolicy).where(
                DecisionPolicy.organization_id == device.organization_id,
                DecisionPolicy.active.is_(True),
            )
        )
    ).scalars().all()
    rules: list[tuple[DecisionPolicy, DecisionRule]] = [
        (policy, rule) for policy in policies for rule in policy.rules
    ]
    if not rules or not candidates:
        return scheduler_winner, []
    rules.sort(key=lambda pair: (pair[1].priority, str(pair[1].id)))

    mandatory: set[str] = set()
    for policy in policies:
        mandatory |= {str(c) for c in policy.guardrails_json.get("mandatory_campaign_ids", [])}

    by_id = {str(c.id): c for c in candidates}
    scores = {str(c.id): float(c.priority) for c in candidates}
    excluded: set[str] = set()
    pinned: str | None = None
    reasons: list[dict] = []

    for _policy, rule in rules:
        matched, condition_notes = await _conditions_match(
            db, device, rule.conditions_json, now_local
        )
        if not matched:
            continue
        actions = rule.actions_json
        target = str(actions.get("pin") or actions.get("boost") or actions.get("exclude"))
        if target not in by_id:
            continue  # rule targets a campaign not eligible right now (guardrail: windows)
        if "exclude" in actions:
            if target in mandatory:
                reasons.append({"rule_id": str(rule.id), "action": "exclude-blocked",
                                "campaign_id": target,
                                "why": "mandatory content guardrail"})
                continue
            excluded.add(target)
            reasons.append({"rule_id": str(rule.id), "action": "exclude",
                            "campaign_id": target, "conditions": condition_notes})
        elif "pin" in actions and pinned is None:
            pinned = target
            reasons.append({"rule_id": str(rule.id), "action": "pin",
                            "campaign_id": target, "conditions": condition_notes})
        elif "boost" in actions:
            amount = actions.get("amount", 10)
            scores[target] += amount
            reasons.append({"rule_id": str(rule.id), "action": "boost",
                            "campaign_id": target, "amount": amount,
                            "conditions": condition_notes})

    if not reasons:
        return scheduler_winner, []

    if pinned is not None and pinned not in excluded:
        winner = by_id[pinned]
    else:
        viable = [c for c in candidates if str(c.id) not in excluded]
        if not viable:
            winner = scheduler_winner  # everything excluded -> ladder falls back
            reasons.append({"action": "fallback", "why": "all candidates excluded"})
        else:
            winner = max(viable, key=lambda c: (scores[str(c.id)], c.priority, str(c.id)))

    # Frequency guardrail (anti-flapping): a "switch" is a CHANGE of the
    # decided campaign vs the device's last logged decision — a sustained
    # identical decision is one switch, not one per manifest build.
    differs = (winner.id if winner else None) != (
        scheduler_winner.id if scheduler_winner else None
    )
    last = (
        await db.execute(
            select(DecisionLog)
            .where(DecisionLog.device_id == device.id)
            .order_by(DecisionLog.decided_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    is_new_change = (
        (last is None and differs)
        or (last is not None and str(last.campaign_id) != str(winner.id if winner else None))
    )
    if is_new_change and differs:
        cap = min(
            (p.guardrails_json.get("max_switches_per_hour",
                                   DEFAULT_GUARDRAILS["max_switches_per_hour"])
             for p in policies),
            default=DEFAULT_GUARDRAILS["max_switches_per_hour"],
        )
        if await _switches_last_hour(db, device.id) >= cap:
            reasons.append({"action": "frequency-capped",
                            "why": f"max {cap} decision switches/hour"})
            winner = scheduler_winner
            is_new_change = False

    if log and is_new_change and differs:
        db.add(
            DecisionLog(
                organization_id=device.organization_id,
                device_id=device.id,
                campaign_id=winner.id if winner else None,
                reason_json={"reasons": reasons,
                             "scheduler_campaign_id": str(scheduler_winner.id)
                             if scheduler_winner else None},
            )
        )
        await db.flush()
    return winner, reasons


async def preview(
    db: AsyncSession,
    organization_id: uuid.UUID,
    device_id: uuid.UUID,
) -> dict:
    """Dry-run for the UI (P3-05): context in → decision + ordered reasons
    out. Never logs."""
    from app.services.manifest import device_effective_timezone
    from app.services.publishing import candidate_campaigns_for_device
    from app.services.scheduling import resolve_active_campaign

    device = (
        await db.execute(
            select(Device).where(
                Device.organization_id == organization_id, Device.id == device_id
            )
        )
    ).scalar_one_or_none()
    if device is None:
        raise NotFoundError("Device not found")

    timezone = await device_effective_timezone(db, device)
    candidates = await candidate_campaigns_for_device(db, device)
    now = datetime.now(UTC)
    import zoneinfo

    now_local = now.astimezone(zoneinfo.ZoneInfo(timezone))
    scheduler_winner = resolve_active_campaign(candidates, now, timezone)
    eligible = [
        c for c in candidates if resolve_active_campaign([c], now, timezone) is not None
    ]
    winner, reasons = await decide(
        db, device, eligible, scheduler_winner, now_local=now_local, log=False
    )
    return {
        "device_id": str(device_id),
        "timezone": timezone,
        "candidates": [
            {"id": str(c.id), "name": c.name, "priority": c.priority,
             "eligible_now": c in eligible}
            for c in candidates
        ],
        "scheduler_campaign_id": str(scheduler_winner.id) if scheduler_winner else None,
        "decided_campaign_id": str(winner.id) if winner else None,
        "reasons": reasons,
    }


async def list_log(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    device_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[DecisionLog], int]:
    query = select(DecisionLog).where(DecisionLog.organization_id == organization_id)
    if device_id:
        query = query.where(DecisionLog.device_id == device_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(DecisionLog.decided_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
