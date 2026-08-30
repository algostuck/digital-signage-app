"""Object storage abstraction (ADR-004).

Two backends behind one interface:
- S3Storage: any S3-compatible endpoint (AWS, MinIO, ...) with real presigned
  URLs. boto3 is imported lazily so local development doesn't require it.
- LocalStorage: disk-backed dev fallback. "Presigned" URLs point at the API's
  own /storage/local endpoints, authorized by an HMAC signature over
  (method, key, expiry) — same contract as S3 from the client's perspective.

Media binaries never touch PostgreSQL either way.
"""

import hashlib
import hmac
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from app.core.config import get_settings


class Storage(Protocol):
    def presigned_put_url(self, key: str, mime_type: str, expires_in: int) -> str: ...
    def presigned_get_url(
        self, key: str, expires_in: int, filename: str | None = None
    ) -> str: ...
    def exists(self, key: str) -> bool: ...
    def read(self, key: str) -> bytes: ...
    def write(self, key: str, data: bytes) -> None: ...
    def delete(self, key: str) -> None: ...


def _local_signature(method: str, key: str, expires_at: int) -> str:
    settings = get_settings()
    message = f"{method}:{key}:{expires_at}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def verify_local_signature(method: str, key: str, expires_at: int, signature: str) -> bool:
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(_local_signature(method, key, expires_at), signature)


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Invalid storage key")
        return path

    def _signed_url(self, method: str, key: str, expires_in: int, extra: str = "") -> str:
        expires_at = int(time.time()) + expires_in
        signature = _local_signature(method, key, expires_at)
        return (
            f"/api/v1/storage/local/{quote(key)}?exp={expires_at}&sig={signature}{extra}"
        )

    def presigned_put_url(self, key: str, mime_type: str, expires_in: int) -> str:
        return self._signed_url("PUT", key, expires_in)

    def presigned_get_url(
        self, key: str, expires_in: int, filename: str | None = None
    ) -> str:
        extra = f"&filename={quote(filename)}" if filename else ""
        return self._signed_url("GET", key, expires_in, extra)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()


class S3Storage:
    def __init__(self):
        import boto3  # lazy: only needed when the s3 backend is configured

        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def presigned_put_url(self, key: str, mime_type: str, expires_in: int) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": mime_type},
            ExpiresIn=expires_in,
        )

    def presigned_get_url(
        self, key: str, expires_in: int, filename: str | None = None
    ) -> str:
        params: dict = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self.client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def write(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        settings = get_settings()
        if settings.storage_backend == "s3":
            _storage = S3Storage()
        else:
            _storage = LocalStorage(settings.local_storage_dir)
    return _storage
