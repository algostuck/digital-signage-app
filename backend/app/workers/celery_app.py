"""Celery application for background jobs.

Queues (grown per slice): media (processing/thumbnails), publishing
(deployment fan-out), maintenance (offline detection, expiry, cleanup).
Run: celery -A app.workers.celery_app worker -l info
Beat: celery -A app.workers.celery_app beat -l info
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "signage",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_track_started=True,
    task_default_queue="default",
    task_routes={
        "app.workers.media.*": {"queue": "media"},
        "app.workers.publishing.*": {"queue": "publishing"},
        "app.workers.maintenance.*": {"queue": "maintenance"},
    },
)


@celery_app.task(name="app.workers.ping")
def ping() -> str:
    return "pong"
