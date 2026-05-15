from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import require_agent_tool_api_key
from app.db.session import get_db
from app.services.database_overview_service import get_customer_related_info, get_database_overview
from app.services.support_operations_service import get_support_operations_dashboard, import_faq_text, import_knowledge_file, update_unanswered_question_status

router = APIRouter(prefix="/api/database", tags=["database"], dependencies=[Depends(require_agent_tool_api_key)])


@router.get("/overview")
def database_overview(industry: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    return get_database_overview(db, industry_key=industry)


@router.get("/customers/{customer_name}/related")
def customer_related_info(
    customer_name: str,
    industry: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return get_customer_related_info(db, customer_name, industry_key=industry)


@router.get("/support/dashboard")
def support_operations_dashboard(db: Session = Depends(get_db)) -> dict[str, object]:
    return get_support_operations_dashboard(db)


@router.post("/support/import-faq")
def support_import_faq(payload: dict[str, object], db: Session = Depends(get_db)) -> dict[str, object]:
    return import_faq_text(
        db,
        text=str(payload.get("text") or ""),
        user_id=str(payload.get("user_id") or "user-demo"),
        source_type=str(payload.get("source_type") or "faq_import"),
        customer_id=str(payload["customer_id"]) if payload.get("customer_id") else None,
        project_id=str(payload["project_id"]) if payload.get("project_id") else None,
    )


@router.post("/support/import-file")
async def support_import_file(
    file: UploadFile = File(...),
    user_id: str = Form(default="user-demo"),
    source_type: str | None = Form(default=None),
    customer_id: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return import_knowledge_file(
            db,
            filename=file.filename or "uploaded-document",
            content=await file.read(),
            user_id=user_id,
            source_type=source_type,
            customer_id=customer_id or None,
            project_id=project_id or None,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/support/unanswered/{unanswered_id}/status")
def support_update_unanswered_status(unanswered_id: str, payload: dict[str, object], db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return update_unanswered_question_status(db, unanswered_id, status=str(payload.get("status") or "pending"))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
