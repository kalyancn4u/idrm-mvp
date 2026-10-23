"""MinIO / S3 wrapper — identical for both apps."""

from __future__ import annotations

import io
import logging
import uuid
from datetime import timedelta
from functools import lru_cache

from minio import Minio

from shared.config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def get_client() -> Minio:
    s = get_settings()
    endpoint = s.s3_endpoint.replace("http://", "").replace("https://", "")
    secure = s.s3_endpoint.startswith("https://")
    return Minio(
        endpoint,
        access_key=s.s3_access_key,
        secret_key=s.s3_secret_key,
        secure=secure,
        region=s.s3_region,
    )


def ensure_bucket() -> None:
    s = get_settings()
    c = get_client()
    if not c.bucket_exists(s.s3_bucket):
        c.make_bucket(s.s3_bucket)


def build_object_key(purpose: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"{purpose}/{uuid.uuid4()}.{ext}"


def upload_bytes(key: str, data: bytes, content_type: str) -> str:
    s = get_settings()
    get_client().put_object(
        s.s3_bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
    )
    return key


def presigned_url(key: str, expires_seconds: int = 3600) -> str:
    s = get_settings()
    return get_client().presigned_get_object(
        s.s3_bucket, key, expires=timedelta(seconds=expires_seconds)
    )


def remove_object(key: str) -> None:
    s = get_settings()
    get_client().remove_object(s.s3_bucket, key)
