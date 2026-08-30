"""AI governance (P3-AI-004/005): per-tenant policies, the explainability
ledger, guardrail checks and the 2A approval adapter for AI outputs."""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.models import AiOutput, AiPolicy, AiRequest
from app.models.ai import AiSafetyStatus

logger = logging.getLogger("app.ai")

POLICY_TYPES = ("operations", "guardrails", "approval")
POLICY_DEFAULTS: dict[str, dict] = {
    "operations": {"allowed": ["text", "creative", "localization"]},
    "guardrails": {"banned_terms": [], "required_disclaimer": None},
    "approval": {"require_approval": False},
}


async def get_policies(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    rows = (
        await db.execute(
            select(AiPolicy).where(
                AiPolicy.organization_id == organization_id, AiPolicy.active.is_(True)
            )
        )
    ).scalars()
    stored = {row.policy_type: row.rules_json for row in rows}
    return {
        policy_type: {**POLICY_DEFAULTS[policy_type], **stored.get(policy_type, {})}
        for policy_type in POLICY_TYPES
    }


def _validate_policy(policy_type: str, rules: dict) -> None:
    if policy_type == "operations":
        allowed = rules.get("allowed")
        if not isinstance(allowed, list) or not all(
            op in ("text", "creative", "localization") for op in allowed
        ):
            raise ValidationAppError(
                "operations.allowed must list text/creative/localization", field=policy_type
            )
    elif policy_type == "guardrails":
        banned = rules.get("banned_terms", [])
        if not isinstance(banned, list) or not all(isinstance(t, str) for t in banned):
            raise ValidationAppError(
                "guardrails.banned_terms must be a list of strings", field=policy_type
            )
    elif policy_type == "approval":
        if not isinstance(rules.get("require_approval", False), bool):
            raise ValidationAppError(
                "approval.require_approval must be a boolean", field=policy_type
            )


async def update_policies(
    db: AsyncSession,
    organization_id: uuid.UUID,
    values: dict,
    *,
    user_id: uuid.UUID | None = None,
) -> dict:
    unknown = set(values) - set(POLICY_TYPES)
    if unknown:
        raise ValidationAppError(f"Unknown policy types: {sorted(unknown)}")
    for policy_type, rules in values.items():
        if not isinstance(rules, dict):
            raise ValidationAppError(f"{policy_type} must be an object", field=policy_type)
        merged = {**POLICY_DEFAULTS[policy_type], **rules}
        _validate_policy(policy_type, merged)
        row = (
            await db.execute(
                select(AiPolicy).where(
                    AiPolicy.organization_id == organization_id,
                    AiPolicy.policy_type == policy_type,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = AiPolicy(organization_id=organization_id, policy_type=policy_type)
            db.add(row)
        row.rules_json = merged
        row.active = True
    await db.flush()

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="AI_POLICIES_UPDATED",
        entity_type="ai_policy",
        entity_id=organization_id,
        after=values,
        user_id=user_id,
    )
    return await get_policies(db, organization_id)


def check_guardrails(policies: dict, text: str) -> str | None:
    """Returns a violation note, or None when the text passes."""
    hits = [
        term
        for term in policies["guardrails"].get("banned_terms", [])
        if term and term.lower() in text.lower()
    ]
    if hits:
        return f"Contains banned terms: {sorted(set(hits))}"
    return None


async def list_requests(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    operation: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AiRequest], int]:
    query = select(AiRequest).where(AiRequest.organization_id == organization_id)
    if operation:
        query = query.where(AiRequest.operation == operation)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(
        query.order_by(AiRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def get_request(
    db: AsyncSession, organization_id: uuid.UUID, request_id: uuid.UUID
) -> AiRequest:
    request = (
        await db.execute(
            select(AiRequest).where(
                AiRequest.organization_id == organization_id, AiRequest.id == request_id
            )
        )
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError("AI request not found")
    return request


# --- 2A approval adapter: ai_output rides the same inbox as campaigns ---


async def _output(db: AsyncSession, organization_id: uuid.UUID, output_id: uuid.UUID) -> AiOutput:
    output = (
        await db.execute(
            select(AiOutput).where(
                AiOutput.organization_id == organization_id, AiOutput.id == output_id
            )
        )
    ).scalar_one_or_none()
    if output is None:
        raise NotFoundError("AI output not found")
    return output


async def _output_name(
    db: AsyncSession, organization_id: uuid.UUID, output_id: uuid.UUID
) -> str | None:
    output = await _output(db, organization_id, output_id)
    text = output.content_json.get("text") or output.content_json.get("headline") or ""
    return f"AI {output.output_kind}: {str(text)[:60]}"


async def _output_on_approved(
    db: AsyncSession, organization_id: uuid.UUID, output_id: uuid.UUID
) -> None:
    output = await _output(db, organization_id, output_id)
    output.safety_status = AiSafetyStatus.PASSED.value
    await db.flush()


async def _output_on_rejected(
    db: AsyncSession, organization_id: uuid.UUID, output_id: uuid.UUID
) -> None:
    output = await _output(db, organization_id, output_id)
    output.safety_status = AiSafetyStatus.REJECTED.value
    await db.flush()


def _register_ai_output_adapter() -> None:
    from app.services import approvals

    approvals.register_adapter(
        "ai_output",
        approvals.EntityAdapter(
            approve_permission="content.edit",
            get_name=_output_name,
            on_approved=_output_on_approved,
            on_rejected=_output_on_rejected,
        ),
    )


_register_ai_output_adapter()
