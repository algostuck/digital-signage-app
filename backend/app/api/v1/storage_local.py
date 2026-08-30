"""Disk-backed storage transfer endpoints — LocalStorage backend only.

These stand in for S3 presigned URLs in development: authorization is the
HMAC signature minted by LocalStorage, not a bearer token (players and
browsers hit these exactly like they would hit S3).
"""

import mimetypes

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.integrations.storage import LocalStorage, get_storage, verify_local_signature

router = APIRouter(prefix="/storage/local")


def _local_storage() -> LocalStorage:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise NotFoundError("Local storage endpoints are disabled")
    return storage


@router.put("/{key:path}")
async def upload_object(
    key: str,
    request: Request,
    exp: int = Query(...),
    sig: str = Query(...),
) -> dict:
    storage = _local_storage()
    if not verify_local_signature("PUT", key, exp, sig):
        raise ForbiddenError("Invalid or expired upload signature")
    data = await request.body()
    settings = get_settings()
    if len(data) > settings.max_upload_size_mb * 1024 * 1024:
        raise ValidationAppError("Upload exceeds the maximum allowed size")
    storage.write(key, data)
    return {"stored": True, "size": len(data)}


@router.get("/{key:path}")
async def download_object(
    key: str,
    exp: int = Query(...),
    sig: str = Query(...),
    filename: str | None = Query(None),
) -> Response:
    storage = _local_storage()
    if not verify_local_signature("GET", key, exp, sig):
        raise ForbiddenError("Invalid or expired download signature")
    if not storage.exists(key):
        raise NotFoundError("Object not found")
    data = storage.read(key)
    media_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    headers = {}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=data, media_type=media_type, headers=headers)
