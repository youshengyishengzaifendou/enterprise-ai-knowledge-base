from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class Actor(BaseModel):
    channel: str
    external_user_id: str
    internal_user_id: str | None = None


class Trace(BaseModel):
    conversation_id: str | None = None
    message_id: str | None = None
    source_url: str | None = None


class AgentToolRequest(BaseModel):
    actor: Actor
    trace: Trace = Field(default_factory=Trace)
    input: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    type: str
    id: str
    title: str
    updated_at: datetime | None = None


class ConfirmationPayload(BaseModel):
    confirmation_id: str
    title: str
    summary: str
    expires_at: datetime | None = None


class AgentToolResponse(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    citations: list[Citation] = Field(default_factory=list)
    need_confirmation: bool = False
    confirmation: ConfirmationPayload | None = None
    message: str
    error_code: str | None = None


class NextActionDraft(BaseModel):
    title: str
    due_date: date | None = None
    owner_hint: str | None = None


class RiskDraft(BaseModel):
    risk_title: str
    risk_detail: str | None = None
    risk_level: str = "medium"


class ExtractedProjectUpdate(BaseModel):
    customer_name: str | None = None
    project_name: str | None = None
    event_type: str = "客户沟通"
    title: str
    summary: str
    detail: str | None = None
    event_time: datetime
    next_actions: list[NextActionDraft] = Field(default_factory=list)
    risks: list[RiskDraft] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = 0.0

