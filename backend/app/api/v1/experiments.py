"""Experimentation API (P3-DEC-003, slice 3B-3)."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser, require_permissions
from app.db.session import get_db
from app.schemas.envelope import success
from app.services import experiments as service

router = APIRouter(prefix="/experiments")


class ArmIn(BaseModel):
    variant_id: uuid.UUID
    allocation_pct: int = Field(ge=1, le=100)


class ExperimentCreate(BaseModel):
    campaign_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    arms: list[ArmIn] = Field(min_length=1)


class TransitionIn(BaseModel):
    action: str  # start | stop


def _experiment_out(experiment) -> dict:
    allocated = sum(arm.allocation_pct for arm in experiment.variants)
    return {
        "id": str(experiment.id),
        "campaign_id": str(experiment.campaign_id),
        "name": experiment.name,
        "status": experiment.status,
        "start_at": experiment.start_at.isoformat() if experiment.start_at else None,
        "end_at": experiment.end_at.isoformat() if experiment.end_at else None,
        "control_pct": 100 - allocated,
        "arms": [
            {"variant_id": str(arm.variant_id), "allocation_pct": arm.allocation_pct}
            for arm in experiment.variants
        ],
    }


@router.get("", dependencies=[require_permissions("campaigns.view")])
async def list_experiments(
    tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    experiments = await service.list_experiments(db, tenant_id)
    return success([_experiment_out(e) for e in experiments])


@router.post("", dependencies=[require_permissions("campaigns.manage")], status_code=201)
async def create_experiment(
    body: ExperimentCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    experiment = await service.create_experiment(
        db,
        tenant_id,
        campaign_id=body.campaign_id,
        name=body.name,
        arms=[{"variant_id": str(arm.variant_id), "allocation_pct": arm.allocation_pct}
              for arm in body.arms],
        user_id=user.id,
    )
    return success(_experiment_out(experiment))


@router.post(
    "/{experiment_id}/transition", dependencies=[require_permissions("campaigns.manage")]
)
async def transition(
    experiment_id: uuid.UUID,
    body: TransitionIn,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    experiment = await service.transition(
        db, tenant_id, experiment_id, action=body.action, user_id=user.id
    )
    return success(_experiment_out(experiment))


@router.delete("/{experiment_id}", dependencies=[require_permissions("campaigns.manage")])
async def delete_experiment(
    experiment_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    await service.delete_experiment(db, tenant_id, experiment_id)
    return success({"deleted": True})


@router.get("/{experiment_id}/results", dependencies=[require_permissions("campaigns.view")])
async def results(
    experiment_id: uuid.UUID, tenant_id: CurrentTenantId, db: AsyncSession = Depends(get_db)
) -> dict:
    return success(await service.results(db, tenant_id, experiment_id))
