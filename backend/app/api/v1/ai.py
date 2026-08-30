"""AI content intelligence API (P3-M01, slice 3B-1).

Permission AND entitlement per the platform pattern; the `ai_features`
entitlement + credit metering are enforced inside the service."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, PageParams, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import ai as ai_service

router = APIRouter(prefix="/ai")


class GenerateTextRequest(BaseModel):
    template: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=2000)
    max_chars: int | None = Field(default=None, ge=8, le=2000)


class GenerateCreativeRequest(BaseModel):
    headline: str = Field(min_length=1, max_length=500)
    body: str | None = Field(default=None, max_length=2000)
    width: int = Field(ge=16, le=16384)
    height: int = Field(ge=16, le=16384)


class LocalizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target_locale: str = Field(min_length=2, max_length=20)


def _request_out(request) -> dict:
    return {
        "id": str(request.id),
        "operation": request.operation,
        "provider": request.provider,
        "model_ref": request.model_ref,
        "template_version": request.template_version,
        "status": request.status,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "outputs": [
            {
                "id": str(output.id),
                "kind": output.output_kind,
                "content": output.content_json,
                "confidence": float(output.confidence),
                "fallback": output.fallback,
                "safety_status": output.safety_status,
                "safety_notes": output.safety_notes,
                "revision_no": output.revision_no,
            }
            for output in request.outputs
        ],
    }


@router.post("/generate/text", dependencies=[require_permissions("content.create")])
async def generate_text(
    body: GenerateTextRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    request = await ai_service.generate_text(
        db, tenant_id,
        template=body.template, text=body.text, max_chars=body.max_chars,
        actor_id=user.id,
    )
    return success(_request_out(request))


@router.post("/generate/creative", dependencies=[require_permissions("layouts.manage")])
async def generate_creative(
    body: GenerateCreativeRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    request = await ai_service.generate_creative(
        db, tenant_id,
        headline=body.headline, body=body.body, width=body.width, height=body.height,
        actor_id=user.id,
    )
    return success(_request_out(request))


@router.post("/localize", dependencies=[require_permissions("content.create")])
async def localize(
    body: LocalizeRequest,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    request = await ai_service.localize(
        db, tenant_id, text=body.text, target_locale=body.target_locale, actor_id=user.id
    )
    return success(_request_out(request))


@router.get("/policies", dependencies=[require_permissions("settings.manage")])
async def get_policies(tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)) -> dict:
    from app.services import entitlements

    await entitlements.require_feature(db, tenant_id, "ai_features")
    return success(await ai_service.get_policies(db, tenant_id))


@router.put("/policies", dependencies=[require_permissions("settings.manage")])
async def update_policies(
    body: dict,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services import entitlements

    await entitlements.require_feature(db, tenant_id, "ai_features")
    return success(await ai_service.update_policies(db, tenant_id, body, user_id=user.id))


@router.get("/requests", dependencies=[require_permissions("content.view")])
async def list_requests(
    tenant_id: CurrentTenantId,
    page: PageParams,
    db: AsyncSession = Depends(get_db),
    operation: str | None = Query(default=None),
) -> dict:
    requests, total = await ai_service.list_requests(
        db, tenant_id, operation=operation, page=page.page, page_size=page.page_size
    )
    return success(
        [_request_out(r) for r in requests],
        page=page.page, page_size=page.page_size, total=total,
    )


@router.get("/requests/{request_id}", dependencies=[require_permissions("content.view")])
async def get_request(
    request_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    request = await ai_service.get_request(db, tenant_id, request_id)
    return success(_request_out(request))
