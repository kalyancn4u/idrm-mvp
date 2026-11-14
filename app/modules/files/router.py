"""Files router — upload to MinIO + presigned download."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db
from app.core.exceptions import AppError
from shared import storage
from shared.audit import log_async
from shared.config import get_settings
from shared.enums import FilePurpose
from shared.models.file import File as FileRow

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]

ALLOWED = {"image/jpeg", "image/png", "image/webp", "application/pdf"}

# Roles that may open files uploaded by someone else (to see request photos
# and completion proof). A citizen may open only their own uploads.
MAY_READ_ANY = frozenset({"provider", "coordinator", "admin"})


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    db: DbSession,
    claims: Claims,
    file: Annotated[UploadFile, File()],
    purpose: Annotated[FilePurpose, Form()],
    entity_type: Annotated[str | None, Form(max_length=30)] = None,
    entity_id: Annotated[uuid.UUID | None, Form()] = None,
):
    # Everything is validated BEFORE anything is written to storage, so a
    # rejected request leaves no orphan object behind.
    settings = get_settings()
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED:
        raise AppError(415, "unsupported_media_type",
                       f"Content type '{content_type}' is not allowed.")

    # Read one byte more than the limit: enough to know it is too big without
    # holding an arbitrarily large upload in memory.
    data = await file.read(settings.file_max_bytes + 1)
    if len(data) > settings.file_max_bytes:
        raise AppError(413, "file_too_large", "File exceeds the size limit.")

    uploader = uuid.UUID(claims["sub"])
    storage.ensure_bucket()
    key = storage.build_object_key(purpose.value, file.filename or "upload.bin")
    storage.upload_bytes(key, data, content_type)

    row = FileRow(
        uploaded_by=uploader,
        bucket=settings.s3_bucket, object_key=key,
        content_type=content_type, size_bytes=len(data),
        purpose=purpose, entity_type=entity_type, entity_id=entity_id,
    )
    db.add(row)
    await db.flush()
    await log_async(db, actor_id=uploader, action="file.uploaded",
                    resource_type="file", resource_id=row.id,
                    new_values={"purpose": purpose.value, "size": len(data)})
    return {"id": str(row.id), "object_key": key}


@router.get("/{file_id}/download")
async def download(file_id: uuid.UUID, db: DbSession, claims: Claims):
    row = await db.get(FileRow, file_id)
    if row is None:
        raise AppError(404, "not_found", "File not found.")
    is_owner = row.uploaded_by == uuid.UUID(claims["sub"])
    if not is_owner and claims.get("role") not in MAY_READ_ANY:
        raise AppError(403, "forbidden", "You may not download this file.")
    return {"url": storage.presigned_url(row.object_key)}
