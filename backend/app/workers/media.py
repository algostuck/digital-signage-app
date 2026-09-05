"""Celery media-processing tasks (queue: media)."""

import asyncio
import uuid

from app.workers.celery_app import celery_app


async def _process(version_id: str) -> None:
    from app.db.session import get_session_factory
    from app.services import media

    async with get_session_factory()() as db:
        await media.process_version(db, uuid.UUID(version_id))
        await db.commit()


@celery_app.task(
    name="app.workers.media.process_asset_version",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_asset_version(self, version_id: str) -> str:
    from app.workers.instrumentation import job_context

    with job_context(
        "media.process_asset_version",
        self.request.id,
        version_id=version_id,
        attempt=self.request.retries,
    ):
        try:
            asyncio.run(_process(version_id))
        except Exception as exc:  # transient infra failures retry with backoff
            raise self.retry(exc=exc) from exc
    return version_id
