from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_agent_tool_api_key
from app.db.session import get_db
from app.services.database_overview_service import get_customer_related_info, get_database_overview

router = APIRouter(prefix="/api/database", tags=["database"], dependencies=[Depends(require_agent_tool_api_key)])


@router.get("/overview")
def database_overview(db: Session = Depends(get_db)) -> dict[str, object]:
    return get_database_overview(db)


@router.get("/customers/{customer_name}/related")
def customer_related_info(customer_name: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return get_customer_related_info(db, customer_name)
