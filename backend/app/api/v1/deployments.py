import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, PageParams, require_permissions
from app.db.session import get_db
from app.models import Deployment
from app.schemas.campaigns import DeploymentDeviceOut, DeploymentOut
from app.schemas.envelope import success
from app.services import publishing
from app.services.campaigns import get_campaign

router = APIRouter()


async def deployment_out(db: AsyncSession, tenant_id: uuid.UUID, deployment: Deployment) -> dict:
    out = DeploymentOut.model_validate(deployment)
    campaign = await get_campaign(db, tenant_id, deployment.campaign_id)
    out.campaign_name = campaign.name
    states = [row.status for row in deployment.devices]
    out.total_devices = len(states)
    out.acknowledged = states.count("acknowledged")
    out.failed = states.count("failed")
    out.pending = states.count("pending")
    return out.model_dump(mode="json")


@router.get("/deployments", dependencies=[require_permissions("deployments.view")])
async def list_deployments(
    tenant_id: CurrentTenantId,
    pagination: PageParams,
    campaign_id: uuid.UUID | None = None,
    status: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deployments, total = await publishing.list_deployments(
        db,
        tenant_id,
        campaign_id=campaign_id,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return success(
        [await deployment_out(db, tenant_id, d) for d in deployments],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/deployments/{deployment_id}", dependencies=[require_permissions("deployments.view")])
async def get_deployment(
    deployment_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    deployment = await publishing.get_deployment(db, tenant_id, deployment_id)
    return success(await deployment_out(db, tenant_id, deployment))


@router.get(
    "/deployments/{deployment_id}/devices",
    dependencies=[require_permissions("deployments.view")],
)
async def deployment_devices(
    deployment_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    from app.repositories import devices as devices_repo

    deployment = await publishing.get_deployment(db, tenant_id, deployment_id)
    devices = await devices_repo.get_by_ids(
        db, tenant_id, [row.device_id for row in deployment.devices]
    )
    names = {d.id: d.name for d in devices}
    rows = []
    for row in deployment.devices:
        out = DeploymentDeviceOut.model_validate(row)
        out.device_name = names.get(row.device_id, "")
        rows.append(out.model_dump(mode="json"))
    return success(rows)


@router.post(
    "/deployments/{deployment_id}/retry",
    dependencies=[require_permissions("deployments.manage")],
)
async def retry_deployment(
    deployment_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    deployment = await publishing.retry_deployment(db, tenant_id, deployment_id)
    return success(await deployment_out(db, tenant_id, deployment))


@router.post(
    "/deployments/{deployment_id}/cancel",
    dependencies=[require_permissions("deployments.manage")],
)
async def cancel_deployment(
    deployment_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    deployment = await publishing.cancel_deployment(db, tenant_id, deployment_id)
    return success(await deployment_out(db, tenant_id, deployment))
