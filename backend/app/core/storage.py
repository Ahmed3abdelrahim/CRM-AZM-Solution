from __future__ import annotations

import io
import uuid
from functools import lru_cache

from minio import Minio

from app.config import settings


@lru_cache
def _client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _ensure_bucket() -> None:
    client = _client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def put_object(data: bytes, content_type: str, *, prefix: str) -> str:
    """Synchronous MinIO (S3 API) upload — the `minio` SDK has no async client, so every
    caller runs this via `asyncio.to_thread` to avoid blocking the event loop. Returns the
    object key stored in `attachments.storage_key`; the key is namespaced under `prefix`
    (e.g. "customers/<customer_id>", "tickets/<ticket_id>") purely for readability in the
    bucket browser — it carries no scoping meaning of its own."""
    _ensure_bucket()
    key = f"{prefix}/{uuid.uuid4()}"
    _client().put_object(
        settings.MINIO_BUCKET, key, io.BytesIO(data), length=len(data), content_type=content_type
    )
    return key
