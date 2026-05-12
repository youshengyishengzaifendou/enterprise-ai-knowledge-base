import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(120))
    request_payload_json: Mapped[str] = mapped_column("request_payload", Text, nullable=False, default="{}")
    response_summary: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def request_payload(self) -> dict:
        return json.loads(self.request_payload_json or "{}")

    @request_payload.setter
    def request_payload(self, value: dict) -> None:
        self.request_payload_json = json.dumps(value, ensure_ascii=False, default=str)

