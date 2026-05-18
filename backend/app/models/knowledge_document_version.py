import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeDocumentVersion(Base):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_knowledge_document_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeConflictReport(Base):
    __tablename__ = "knowledge_conflict_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    related_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    conflict_type: Mapped[str] = mapped_column(String(80), nullable=False, default="possible_conflict")
    detail: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
