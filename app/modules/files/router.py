"""Files router — upload to MinIO + presigned download."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, get_optional_claims
from app.core.exceptions import AppError
from app.core.pagination import paginate
from shared import storage
from shared.audit import log_async
from shared.config import get_settings
from shared.db import async_session
from shared.models.file import File as FileRow

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]
OptClaims = Annotated[dict | None, Depends(get_optional_claims)]

ALLOWED = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    db: DbSession,
    file: UploadFile = File(...),
    purpose: str = Form(...),
    entity_type: str | None = Form(None),
    entity_id: uuid.UUID | None = Form(None),
    claims: OptClaims = None,
):
    settings = get_settings()
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED:
        raise AppError(415, "unsupported_media_type",
                       f"Content type '{content_type}' is not allowed.")
    data = await file.read()
    if len(data) > settings.file_max_bytes:
        raise AppError(413, "file_too_large", "File exceeds the size limit.")

    storage.ensure_bucket()
    key = storage.build_object_key(purpose, file.filename or "upload.bin")
    storage.upload_bytes(key, data, content_type)

    row = FileRow(
        uploaded_by=uuid.UUID(claims["sub"]) if claims else None,
        bucket=settings.s3_bucket, object_key=key,
        content_type=content_type, size_bytes=len(data),
        purpose=purpose, entity_type=entity_type, entity_id=entity_id,
    )
    db.add(row)
    await db.flush()
    await log_async(db, actor_id=row.uploaded_by, action="file.uploaded",
                    resource_type="file", resource_id=row.id,
                    new_values={"purpose": purpose, "size": len(data)})
    return {"id": str(row.id), "object_key": key}


@router.get("/{file_id}/download")
async def download(file_id: uuid.UUID, db: DbSession):
    row = await db.get(FileRow, file_id)
    if row is None:
        raise AppError(404, "not_found", "File not found.")
    return {"url": storage.presigned_url(row.object_key)}

