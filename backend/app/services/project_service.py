from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Project, ProjectEvent, ProjectRisk, ProjectTask, User
from app.schemas.agent_tools import Citation
from app.services.permission_service import can_access_customer, can_access_project


def _matches_aliases(aliases: list[str], query: str) -> bool:
    return any(query.lower() in alias.lower() for alias in aliases)


def search_customers(db: Session, query: str, user: User | None = None) -> list[Customer]:
    rows = db.scalars(select(Customer).where(Customer.status == "active")).all()
    matches = [row for row in rows if query.lower() in row.name.lower() or _matches_aliases(row.aliases, query)]
    if user is None:
        return matches
    return [row for row in matches if can_access_customer(db, user, row)]


def search_projects(db: Session, query: str, customer_id: str | None = None, user: User | None = None) -> list[Project]:
    stmt = select(Project).where(Project.status == "active")
    if customer_id:
        stmt = stmt.where(Project.customer_id == customer_id)
    rows = db.scalars(stmt).all()
    matches = [row for row in rows if query.lower() in row.name.lower() or _matches_aliases(row.aliases, query)]
    if user is None:
        return matches
    return [row for row in matches if can_access_project(db, user, row)]


def create_project_event(db: Session, *, payload: dict[str, Any], user_id: str, source_url: str | None) -> ProjectEvent:
    project = db.get(Project, payload["project_id"])
    if project is None:
        raise ValueError("PROJECT_NOT_FOUND")
    event = ProjectEvent(
        project_id=project.id,
        customer_id=project.customer_id,
        event_type=payload.get("event_type", "客户沟通"),
        title=payload["title"],
        summary=payload["summary"],
        detail=payload.get("detail"),
        source_type=payload.get("source_type", "chat"),
        source_url=source_url,
        created_by=user_id,
        event_time=datetime.fromisoformat(payload["event_time"]) if isinstance(payload["event_time"], str) else payload["event_time"],
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_project_task(db: Session, *, payload: dict[str, Any], user_id: str) -> ProjectTask:
    project = db.get(Project, payload["project_id"])
    if project is None:
        raise ValueError("PROJECT_NOT_FOUND")
    due_date = payload.get("due_date")
    if isinstance(due_date, str):
        due_date = date.fromisoformat(due_date)
    task = ProjectTask(
        project_id=project.id,
        customer_id=project.customer_id,
        title=payload["title"],
        description=payload.get("description"),
        owner_user_id=payload.get("owner_user_id"),
        due_date=due_date,
        created_by=user_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_project_brief(db: Session, project_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("PROJECT_NOT_FOUND")
    events = db.scalars(
        select(ProjectEvent).where(ProjectEvent.project_id == project_id).order_by(ProjectEvent.event_time.desc()).limit(5)
    ).all()
    tasks = db.scalars(
        select(ProjectTask).where(ProjectTask.project_id == project_id, ProjectTask.status != "done").order_by(ProjectTask.created_at.desc())
    ).all()
    risks = db.scalars(
        select(ProjectRisk).where(ProjectRisk.project_id == project_id, ProjectRisk.status == "open").order_by(ProjectRisk.created_at.desc())
    ).all()
    citations = [
        Citation(type="project_event", id=event.id, title=event.title, updated_at=event.event_time)
        for event in events
    ]
    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "stage": project.stage,
            "status": project.status,
            "owner_user_id": project.owner_user_id,
            "updated_at": project.updated_at,
        },
        "recent_events": [
            {"id": event.id, "title": event.title, "summary": event.summary, "event_time": event.event_time}
            for event in events
        ],
        "open_tasks": [
            {"id": task.id, "title": task.title, "status": task.status, "due_date": task.due_date, "owner_user_id": task.owner_user_id}
            for task in tasks
        ],
        "open_risks": [
            {"id": risk.id, "risk_title": risk.risk_title, "risk_level": risk.risk_level, "status": risk.status}
            for risk in risks
        ],
        "citations": citations,
    }
