import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeSourceFile(Base):
    __tablename__ = "knowledge_source_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column()
    storage: Mapped[str | None] = mapped_column(String(80))
    uploaded_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_channel: Mapped[str | None] = mapped_column(String(50))
    source_external_user_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeSourceFilePermission(Base):
    __tablename__ = "knowledge_source_file_permissions"
    __table_args__ = (UniqueConstraint("source_file_id", "user_id", name="uq_knowledge_source_file_user_permission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_file_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_source_files.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    access_level: Mapped[str] = mapped_column(String(50), nullable=False, default="read")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
