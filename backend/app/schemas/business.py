from datetime import date, datetime

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    industry: str | None = None
    level: str | None = None
    status: str = "active"
    owner_user_id: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None


class CustomerRead(CustomerCreate):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomerList(BaseModel):
    items: list[CustomerRead]


class ProjectCreate(BaseModel):
    customer_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    stage: str = "需求沟通"
    status: str = "active"
    amount: float | None = None
    owner_user_id: str | None = None
    expected_sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProjectRead(ProjectCreate):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectList(BaseModel):
    items: list[ProjectRead]

