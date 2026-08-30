"""Media processing pipeline (M06): validate -> metadata -> thumbnail -> READY.

Runs inline (dev/test) or inside the Celery media worker; both call
process_version(). Failures never raise out of the pipeline — they land the
version in FAILED with the error recorded (FR-MED-002).
"""

import hashlib
import io
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.storage import get_storage
from app.models import Asset, AssetVersion
from app.models.content import ProcessingStatus
from app.repositories import content as repo

logger = logging.getLogger("app.media")

THUMBNAIL_MAX_PX = 320


def _extract_image_metadata(data: bytes) -> tuple[int, int, bytes | None]:
    """Returns (width, height, thumbnail_png_bytes)."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        thumb = img.convert("RGB")
        thumb.thumbnail((THUMBNAIL_MAX_PX, THUMBNAIL_MAX_PX))
        buffer = io.BytesIO()
        thumb.save(buffer, format="JPEG", quality=80)
        return width, height, buffer.getvalue()


async def process_version(db: AsyncSession, version_id: uuid.UUID) -> AssetVersion:
    version = await repo.get_version(db, version_id)
    if version is None:
        raise ValueError(f"Unknown asset version {version_id}")
    storage = get_storage()

    try:
        data = storage.read(version.object_key)

        # Validate: size on disk must match the declared size.
        if len(data) != version.size_bytes:
            raise ValueError(
                f"Uploaded size {len(data)} does not match declared {version.size_bytes}"
            )

        version.checksum = hashlib.sha256(data).hexdigest()

        if version.mime_type.startswith("image/") and version.mime_type != "image/svg+xml":
            width, height, thumbnail = _extract_image_metadata(data)
            version.width = width
            version.height = height
            if thumbnail is not None:
                thumb_key = f"{version.object_key.rsplit('/', 2)[0]}/thumbnail/thumb.jpg"
                storage.write(thumb_key, thumbnail)
                version.thumbnail_key = thumb_key
        # Video duration/thumbnail extraction is an FFmpeg worker concern;
        # the pipeline records READY with basic metadata until that lands.

        version.processing_status = ProcessingStatus.READY.value
        version.processing_error = None

        asset = await db.get(Asset, version.asset_id)
        if asset is not None:
            asset.checksum = version.checksum
            asset.current_version_id = version.id
    except Exception as exc:
        logger.exception("Processing failed for version %s", version_id)
        version.processing_status = ProcessingStatus.FAILED.value
        version.processing_error = str(exc)[:1000]

    await db.flush()
    return version
