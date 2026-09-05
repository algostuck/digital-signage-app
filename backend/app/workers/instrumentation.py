"""Structured context for background jobs.

Every Celery task runs inside `job_context`, so each log line it emits
carries the job name and task id (in `request_id`, the same field an API
request uses - one grep finds either), and the task's start, outcome,
duration and the ids it worked on are logged in one place. This is what
lets "something failed" become "publishing job 7f3a... for deployment ...
failed after 1.2 s with <error>".
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.context import request_id_ctx, tenant_id_ctx

logger = logging.getLogger("app.jobs")


@contextmanager
def job_context(job: str, task_id: str | None, **fields: object) -> Iterator[dict]:
    """Log start/finish of a job with structured fields. Mutate the yielded
    dict to add result fields (counts, ids) before the job returns."""
    token = request_id_ctx.set(task_id or f"job-{job}")
    tenant_token = None
    if fields.get("tenant_id"):
        tenant_token = tenant_id_ctx.set(fields["tenant_id"])  # type: ignore[arg-type]
    started = time.perf_counter()
    result: dict = {}
    base = {"job": job, "task_id": task_id, **{k: str(v) for k, v in fields.items()}}
    logger.info("job %s started", job, extra={"extra_fields": {**base, "phase": "start"}})
    try:
        yield result
    except Exception as exc:
        logger.exception(
            "job %s failed: %s",
            job,
            exc,
            extra={
                "extra_fields": {
                    **base,
                    "phase": "failed",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "error": str(exc)[:500],
                }
            },
        )
        raise
    else:
        logger.info(
            "job %s finished",
            job,
            extra={
                "extra_fields": {
                    **base,
                    "phase": "finished",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    **{k: str(v) for k, v in result.items()},
                }
            },
        )
    finally:
        request_id_ctx.reset(token)
        if tenant_token is not None:
            tenant_id_ctx.reset(tenant_token)
