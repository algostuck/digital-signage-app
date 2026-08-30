"""AI operations (P3-AI-001/002/003): generate/localize with the
deterministic failure ladder and full governance recording.

Every call: entitlement (`ai_features`) + credit metering
(`ai_credits_month`) → policy check → provider (fallback to deterministic
local on failure) → guardrails → ai_request/ai_output ledger → optional 2A
approval routing.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ValidationAppError
from app.integrations.ai_providers import (
    AIProviderError,
    AIResult,
    LocalDeterministicProvider,
    get_ai_provider,
)
from app.models import AiOutput, AiRequest
from app.models.ai import AiRequestStatus, AiSafetyStatus
from app.services.ai import governance

logger = logging.getLogger("app.ai")


async def _ensure_allowed(
    db: AsyncSession, organization_id: uuid.UUID, operation: str
) -> dict:
    from app.services import entitlements, usage

    await entitlements.require_feature(db, organization_id, "ai_features")
    effective = await entitlements.get_effective(db, organization_id)
    credit_limit = effective.limit("ai_credits_month")
    if credit_limit is not None:
        used = await usage.metered_used(db, organization_id, "ai_credits")
        if used >= credit_limit:
            raise BusinessRuleError(
                f"AI credit limit reached ({used}/{credit_limit}). "
                "Upgrade your subscription."
            )
    policies = await governance.get_policies(db, organization_id)
    if operation not in policies["operations"]["allowed"]:
        raise BusinessRuleError(
            f"AI operation '{operation}' is disabled by your organization's AI policy"
        )
    return policies


def _call_with_ladder(call, local_call) -> tuple[AIResult, bool]:
    """provider ok → result; provider failed → deterministic local result
    marked as fallback (NFR3-06). Raises only when BOTH fail."""
    provider = get_ai_provider()
    try:
        return call(provider), False
    except AIProviderError:
        raise  # deterministic template errors are the caller's bug, not an outage
    except Exception as exc:  # noqa: BLE001 - any transport/provider outage degrades
        logger.warning("AI provider failed, using deterministic fallback: %s", exc)
        return local_call(LocalDeterministicProvider()), True


async def _record(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    operation: str,
    actor_id: uuid.UUID | None,
    result: AIResult,
    fallback: bool,
    policies: dict,
    guardrail_text: str,
) -> AiRequest:
    from app.services import usage

    request = AiRequest(
        organization_id=organization_id,
        actor_id=actor_id,
        operation=operation,
        provider=result.provider,
        model_ref=result.model_ref,
        template_version=result.template_version,
        status=AiRequestStatus.DONE.value,
    )
    db.add(request)
    await db.flush()

    violation = governance.check_guardrails(policies, guardrail_text)
    require_approval = policies["approval"].get("require_approval", False)
    if violation:
        safety = AiSafetyStatus.FLAGGED.value
    elif require_approval:
        safety = AiSafetyStatus.PENDING.value
    else:
        safety = AiSafetyStatus.PASSED.value

    output = AiOutput(
        organization_id=organization_id,
        request_id=request.id,
        output_kind=operation,
        content_json=result.content,
        confidence=result.confidence,
        fallback=fallback,
        safety_status=safety,
        safety_notes=violation or ("; ".join(result.notes) or None),
    )
    db.add(output)
    await db.flush()
    await db.refresh(request, ["outputs"])

    # Approval routing (P3-AI-004): clean outputs enter the 2A inbox when
    # the tenant policy demands it; flagged ones always need human action.
    if safety == AiSafetyStatus.PENDING.value:
        from app.services import approvals

        await approvals.submit(
            db, organization_id, "ai_output", output.id, requester_id=actor_id
        )

    await usage.record_metered(db, organization_id, "ai_credits")

    from app.services import audit

    await audit.record(
        db,
        organization_id,
        action="AI_GENERATED",
        entity_type="ai_request",
        entity_id=request.id,
        after={
            "operation": operation,
            "provider": result.provider,
            "template_version": result.template_version,
            "confidence": result.confidence,
            "safety_status": safety,
            "fallback": fallback,
        },
        user_id=actor_id,
    )
    return request


async def generate_text(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    template: str,
    text: str,
    max_chars: int | None = None,
    actor_id: uuid.UUID | None = None,
) -> AiRequest:
    if not text.strip():
        raise ValidationAppError("text must not be empty", field="text")
    policies = await _ensure_allowed(db, organization_id, "text")
    result, fallback = _call_with_ladder(
        lambda p: p.generate_text(template=template, text=text, max_chars=max_chars),
        lambda p: p.generate_text(template=template, text=text, max_chars=max_chars),
    )
    return await _record(
        db, organization_id, operation="text", actor_id=actor_id,
        result=result, fallback=fallback, policies=policies,
        guardrail_text=result.content.get("text", ""),
    )


async def generate_creative(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    headline: str,
    body: str | None,
    width: int,
    height: int,
    actor_id: uuid.UUID | None = None,
) -> AiRequest:
    if not headline.strip():
        raise ValidationAppError("headline must not be empty", field="headline")
    if not (16 <= width <= 16384 and 16 <= height <= 16384):
        raise ValidationAppError("width/height must be 16..16384", field="width")
    policies = await _ensure_allowed(db, organization_id, "creative")
    result, fallback = _call_with_ladder(
        lambda p: p.generate_creative(headline=headline, body=body, width=width, height=height),
        lambda p: p.generate_creative(headline=headline, body=body, width=width, height=height),
    )
    guardrail_text = " ".join(
        str(v) for v in (result.content.get("headline"), result.content.get("body")) if v
    )
    return await _record(
        db, organization_id, operation="creative", actor_id=actor_id,
        result=result, fallback=fallback, policies=policies,
        guardrail_text=guardrail_text,
    )


async def localize(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    text: str,
    target_locale: str,
    actor_id: uuid.UUID | None = None,
) -> AiRequest:
    if not text.strip():
        raise ValidationAppError("text must not be empty", field="text")
    policies = await _ensure_allowed(db, organization_id, "localization")
    try:
        result, fallback = _call_with_ladder(
            lambda p: p.localize(text=text, target_locale=target_locale),
            lambda p: p.localize(text=text, target_locale=target_locale),
        )
    except AIProviderError as exc:
        raise ValidationAppError(str(exc), field="target_locale") from exc

    # P3-AI-003: localization must never damage placeholders.
    from app.integrations.ai_providers import TOKEN_RE

    original_tokens = sorted(TOKEN_RE.findall(text))
    localized_tokens = sorted(TOKEN_RE.findall(result.content.get("text", "")))
    if original_tokens != localized_tokens:
        raise BusinessRuleError(
            "Localization would alter placeholders — output rejected"
        )
    return await _record(
        db, organization_id, operation="localization", actor_id=actor_id,
        result=result, fallback=fallback, policies=policies,
        guardrail_text=result.content.get("text", ""),
    )
