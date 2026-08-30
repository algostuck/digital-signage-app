"""Celery publishing tasks (queue: publishing)."""

import asyncio
import uuid

from app.workers.celery_app import celery_app


async def _process(deployment_id: str) -> None:
    from app.db.session import get_session_factory
    from app.services import publishing

    async with get_session_factory()() as db:
        await publishing.materialize_deployment(db, uuid.UUID(deployment_id))
        await db.commit()


@celery_app.task(
    name="app.workers.publishing.process_deployment",
    bind=True,
    max_retries=5,
    default_retry_delay=15,
)
def process_deployment(self, deployment_id: str) -> str:
    try:
        asyncio.run(_process(deployment_id))
    except Exception as exc:  # bounded backoff (NFR-005)
        raise self.retry(exc=exc) from exc
    return deployment_id
