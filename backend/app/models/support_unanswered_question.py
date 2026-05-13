import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportUnansweredQuestion(Base):
    __tablename__ = "support_unanswered_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="kb_answer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
