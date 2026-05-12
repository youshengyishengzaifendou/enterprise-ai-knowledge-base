from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor
from app.core.auth import require_agent_tool_api_key
from app.db.session import get_db
from app.models import Customer, Project, User
from app.schemas.business import ProjectCreate, ProjectList, ProjectRead
from app.services.permission_service import can_access_project, can_access_customer

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(require_agent_tool_api_key)])


def _read_project(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        customer_id=project.customer_id,
        name=project.name,
        aliases=project.aliases,
        stage=project.stage,
        status=project.status,
        amount=float(project.amount) if project.amount is not None else None,
        owner_user_id=project.owner_user_id,
        expected_sign_date=project.expected_sign_date,
        start_date=project.start_date,
        end_date=project.end_date,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=ProjectList)
def list_projects(
    query: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_actor),
) -> ProjectList:
    rows = db.scalars(select(Project).where(Project.status == "active")).all()
    items = [
        _read_project(project)
        for project in rows
        if can_access_project(db, user, project)
        and (not query or query.lower() in project.name.lower() or any(query.lower() in alias.lower() for alias in project.aliases))
    ]
    return ProjectList(items=items)


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_actor),
) -> ProjectRead:
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    if not can_access_customer(db, user, customer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    project = Project(
        customer_id=payload.customer_id,
        name=payload.name,
        stage=payload.stage,
        status=payload.status,
        amount=payload.amount,
        owner_user_id=payload.owner_user_id or user.id,
        expected_sign_date=payload.expected_sign_date,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    project.aliases = payload.aliases
    db.add(project)
    db.commit()
    db.refresh(project)
    return _read_project(project)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_actor),
) -> ProjectRead:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if not can_access_project(db, user, project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    return _read_project(project)

