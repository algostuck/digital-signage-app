"""Approval & governance engine (P2-M03).

Polymorphic maker-checker workflow over any entity type. Entity behavior is
registered through adapters; the engine owns policies, request lifecycle,
the immutable action trail, notifications and audit records.

Default (no policy row): approval required, maker-checker OFF — exactly the
Phase-1 behavior, so existing flows remain valid.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, NotFoundError
from app.models import ApprovalAction, ApprovalPolicy, ApprovalRequest, User
from app.models.approval import ApprovalRequestState

logger = logging.getLogger("app.approvals")

SUPPORTED_ENTITY_TYPES = ("campaign", "template", "ai_output", "ad_booking")


@dataclass(frozen=True)
class EntityAdapter:
    """How the engine talks to a concrete entity type."""

    approve_permission: str
    get_name: Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[str | None]]
    on_approved: Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[None]]
    on_rejected: Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[None]]


_ADAPTERS: dict[str, EntityAdapter] = {}


def register_adapter(entity_type: str, adapter: EntityAdapter) -> None:
    _ADAPTERS[entity_type] = adapter


def get_adapter(entity_type: str) -> EntityAdapter:
    adapter = _ADAPTERS.get(entity_type)
    if adapter is None:
        raise NotFoundError(f"No approval support for entity type '{entity_type}'")
    return adapter


# --- policies (P2-APP-001) ---


@dataclass(frozen=True)
class EffectivePolicy:
    entity_type: str
    require_approval: bool
    maker_checker: bool


async def get_policy(
    db: AsyncSession, organization_id: uuid.UUID, entity_type: str
) -> EffectivePolicy:
    row = (
        await db.execute(
            select(ApprovalPolicy).where(
                ApprovalPolicy.organization_id == organization_id,
                ApprovalPolicy.entity_type == entity_type,
                ApprovalPolicy.active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return EffectivePolicy(entity_type, require_approval=True, maker_checker=False)
    return EffectivePolicy(entity_type, row.require_approval, row.maker_checker)


async def upsert_policy(
    db: AsyncSession,
    organization_id: uuid.UUID,
    entity_type: str,
    *,
    require_approval: bool,
    maker_checker: bool,
) -> ApprovalPolicy:
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise BusinessRuleError(f"Unsupported approval entity type '{entity_type}'")
    row = (
        await db.execute(
            select(ApprovalPolicy).where(
                ApprovalPolicy.organization_id == organization_id,
                ApprovalPolicy.entity_type == entity_type,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ApprovalPolicy(organization_id=organization_id, entity_type=entity_type)
        db.add(row)
    row.require_approval = require_approval
    row.maker_checker = maker_checker
    row.active = True
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="APPROVAL_POLICY_UPDATED",
        entity_type="approval_policy",
        entity_id=row.id,
        after={"entity_type": entity_type, "require_approval": require_approval,
               "maker_checker": maker_checker},
    )
    return row


# --- request lifecycle (P2-APP-002/003) ---


def _add_action(
    request: ApprovalRequest,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    comments: str | None,
    from_state: str | None,
    to_state: str | None,
) -> None:
    request.actions.append(
        ApprovalAction(
            approval_request_id=request.id,
            actor_id=actor_id,
            action=action,
            comments=comments,
            from_state=from_state,
            to_state=to_state,
        )
    )


async def open_request_for(
    db: AsyncSession, organization_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
) -> ApprovalRequest | None:
    return (
        await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.organization_id == organization_id,
                ApprovalRequest.entity_type == entity_type,
                ApprovalRequest.entity_id == entity_id,
                ApprovalRequest.state == ApprovalRequestState.PENDING.value,
            )
        )
    ).scalar_one_or_none()


async def submit(
    db: AsyncSession,
    organization_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    *,
    requester_id: uuid.UUID | None,
    comments: str | None = None,
) -> ApprovalRequest:
    """Creates a pending request (superseding any open one). When the tenant
    policy says approval is not required, the request auto-approves and the
    entity transitions immediately."""
    get_adapter(entity_type)
    policy = await get_policy(db, organization_id, entity_type)

    existing = await open_request_for(db, organization_id, entity_type, entity_id)
    if existing is not None:
        existing.state = ApprovalRequestState.SUPERSEDED.value
        _add_action(
            existing,
            actor_id=requester_id,
            action="superseded",
            comments="Superseded by a new submission",
            from_state=ApprovalRequestState.PENDING.value,
            to_state=ApprovalRequestState.SUPERSEDED.value,
        )

    request = ApprovalRequest(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        requester_id=requester_id,
        submitted_at=datetime.now(UTC),
    )
    db.add(request)
    await db.flush()
    await db.refresh(request, ["actions"])
    _add_action(
        request,
        actor_id=requester_id,
        action="submitted",
        comments=comments,
        from_state=None,
        to_state=ApprovalRequestState.PENDING.value,
    )
    await db.flush()

    if not policy.require_approval:
        await _decide(
            db,
            request,
            actor=None,
            approve=True,
            comments="Auto-approved: tenant policy does not require approval",
            enforce_maker_checker=False,
        )
        return request

    from app.services import notifications

    adapter = get_adapter(entity_type)
    name = await adapter.get_name(db, organization_id, entity_id)
    await notifications.create(
        db,
        organization_id,
        type="APPROVAL_REQUESTED",
        title=f"{entity_type.capitalize()} '{name}' awaits approval",
        message=comments or "Review and approve or reject the submission.",
        payload={"approval_request_id": str(request.id), "entity_type": entity_type,
                 "entity_id": str(entity_id)},
    )
    logger.info("Approval requested: %s %s (request %s)", entity_type, entity_id, request.id)
    return request


async def get_request(
    db: AsyncSession, organization_id: uuid.UUID, request_id: uuid.UUID
) -> ApprovalRequest:
    request = (
        await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.organization_id == organization_id,
                ApprovalRequest.id == request_id,
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError("Approval request not found")
    return request


async def _decide(
    db: AsyncSession,
    request: ApprovalRequest,
    *,
    actor: User | None,
    approve: bool,
    comments: str | None,
    enforce_maker_checker: bool = True,
) -> ApprovalRequest:
    if request.state != ApprovalRequestState.PENDING.value:
        raise BusinessRuleError("This approval request has already been decided")

    if enforce_maker_checker and actor is not None:
        policy = await get_policy(db, request.organization_id, request.entity_type)
        if policy.maker_checker and request.requester_id == actor.id:
            raise BusinessRuleError(
                "Maker-checker is enabled: the submitter cannot decide their own request"
            )

    from_state = request.state
    request.state = (
        ApprovalRequestState.APPROVED.value if approve else ApprovalRequestState.REJECTED.value
    )
    request.decided_at = datetime.now(UTC)
    request.decided_by = actor.id if actor else None
    request.comments = comments
    _add_action(
        request,
        actor_id=actor.id if actor else None,
        action="approved" if approve else "rejected",
        comments=comments,
        from_state=from_state,
        to_state=request.state,
    )
    await db.flush()

    adapter = get_adapter(request.entity_type)
    if approve:
        await adapter.on_approved(db, request.organization_id, request.entity_id)
    else:
        await adapter.on_rejected(db, request.organization_id, request.entity_id)

    from app.services import audit, notifications

    await audit.record(
        db,
        request.organization_id,
        action="APPROVAL_APPROVED" if approve else "APPROVAL_REJECTED",
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        after={"approval_request_id": str(request.id), "comments": comments},
        user_id=actor.id if actor else None,
    )
    if request.requester_id is not None and actor is not None:
        name = await adapter.get_name(db, request.organization_id, request.entity_id)
        await notifications.create(
            db,
            request.organization_id,
            type="APPROVAL_DECIDED",
            severity="info" if approve else "warning",
            title=(
                f"{request.entity_type.capitalize()} '{name}' was "
                f"{'approved' if approve else 'rejected'}"
            ),
            message=comments,
            user_id=request.requester_id,
            payload={"approval_request_id": str(request.id)},
        )
    logger.info(
        "Approval %s: %s %s by %s",
        request.state,
        request.entity_type,
        request.entity_id,
        actor.id if actor else "system",
    )
    return request


async def decide(
    db: AsyncSession,
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    *,
    actor: User,
    approve: bool,
    comments: str | None,
) -> ApprovalRequest:
    request = await get_request(db, organization_id, request_id)
    return await _decide(db, request, actor=actor, approve=approve, comments=comments)


async def decide_for_entity(
    db: AsyncSession,
    organization_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    *,
    actor: User,
    approve: bool,
    comments: str | None = None,
) -> ApprovalRequest | None:
    """Backward-compatible path for legacy per-entity approve/reject
    endpoints. Falls back to a direct adapter transition when no request
    exists (entities submitted before the engine was introduced)."""
    request = await open_request_for(db, organization_id, entity_type, entity_id)
    if request is not None:
        return await _decide(db, request, actor=actor, approve=approve, comments=comments)
    adapter = get_adapter(entity_type)
    if approve:
        await adapter.on_approved(db, organization_id, entity_id)
    else:
        await adapter.on_rejected(db, organization_id, entity_id)
    return None


async def inbox(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    state: str | None,
    entity_type: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ApprovalRequest], int]:
    query = select(ApprovalRequest).where(
        ApprovalRequest.organization_id == organization_id
    )
    if state:
        query = query.where(ApprovalRequest.state == state)
    if entity_type:
        query = query.where(ApprovalRequest.entity_type == entity_type)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(ApprovalRequest.submitted_at.desc(), ApprovalRequest.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total
