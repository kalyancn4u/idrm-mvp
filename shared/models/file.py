"""Files — metadata only. Bytes live in MinIO."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import FilePurpose
from shared.models.base import Base, UUIDPrimaryKey

file_purpose_enum = SAEnum(FilePurpose, name="file_purpose")


class File(UUIDPrimaryKey, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint("size_bytes <= 10485760", name="ck_files_size_max"),
    )

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024))
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    purpose: Mapped[FilePurpose] = mapped_column(file_purpose_enum, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

