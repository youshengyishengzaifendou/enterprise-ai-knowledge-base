from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor, get_management_actor
from app.core.auth import require_agent_tool_api_key
from app.db.session import get_db
from app.models import KnowledgeDocument, KnowledgeSourceFile, Project, User
from app.schemas.agent_tools import Actor
from app.services.database_overview_service import get_customer_related_info, get_database_overview
from app.services.identity_service import resolve_actor
from app.services.knowledge_permission_service import can_access_source_file
from app.services.knowledge_service import (
    add_document_to_group,
    backfill_source_files,
    batch_grant_documents,
    create_document_group,
    grant_project_permission,
    grant_source_file_permission,
    publish_document,
    rebuild_document_index,
    reject_document,
)
from app.services.permission_operations_service import disable_user, grant_document_permission, sync_channel_account_alias
from app.services.support_operations_service import get_support_operations_dashboard, import_faq_text, import_knowledge_file, update_unanswered_question_status

router = APIRouter(prefix="/api/database", tags=["database"], dependencies=[Depends(require_agent_tool_api_key)])
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _serialize_user_summary(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "name": user.name,
        "knowledge_access_policy": user.knowledge_access_policy,
        "status": user.status,
    }


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


@router.post("/knowledge/{document_id}/rebuild-index")
def knowledge_rebuild_index(document_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return rebuild_document_index(db, document_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/knowledge/{document_id}/publish")
def knowledge_publish(
    document_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    try:
        return publish_document(db, document_id, reviewer_user_id=actor.id)
    except ValueError as error:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(error) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.post("/knowledge/{document_id}/reject")
def knowledge_reject(
    document_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    try:
        return reject_document(db, document_id, reviewer_user_id=actor.id, reason=str(payload.get("reason") or "") or None)
    except ValueError as error:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(error) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.post("/knowledge/source-files/backfill")
def knowledge_backfill_source_files(
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    return {"ok": True, **backfill_source_files(db)}


@router.post("/users/{user_id}/knowledge-policy")
def user_update_knowledge_policy(
    user_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    policy = str(payload.get("knowledge_access_policy") or "").strip()
    if policy not in {"all", "own"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="knowledge_access_policy must be all or own")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    user.knowledge_access_policy = policy
    db.commit()
    db.refresh(user)
    return {"ok": True, "user": _serialize_user_summary(user)}


@router.post("/users/channel-accounts/sync")
def user_sync_channel_accounts(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    channel = str(payload.get("channel") or "").strip()
    raw_account_ids = payload.get("account_ids")
    raw_accounts = payload.get("accounts")
    if channel not in {"feishu", "openclaw-weixin"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="channel must be feishu or openclaw-weixin")
    if raw_accounts is None and not isinstance(raw_account_ids, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="account_ids must be a list")

    synced = []
    skipped = []
    skipped_details = []
    account_items = raw_accounts if isinstance(raw_accounts, list) else []
    for raw_account in account_items:
        if not isinstance(raw_account, dict):
            continue
        account_id = str(raw_account.get("account_id") or "").strip()
        alias_user_id = str(raw_account.get("user_id") or "").strip()
        if not account_id or not alias_user_id:
            continue
        try:
            user = sync_channel_account_alias(db, channel=channel, account_id=account_id, alias_user_id=alias_user_id)
        except ValueError as error:
            skipped.append(account_id)
            skipped_details.append({"account_id": account_id, "reason": str(error)})
            continue
        synced.append(_serialize_user_summary(user))

    for raw_account_id in raw_account_ids if isinstance(raw_account_ids, list) else []:
        account_id = str(raw_account_id or "").strip()
        if not account_id:
            continue
        user = resolve_actor(db, Actor(channel=channel, external_user_id=account_id))
        if user is None:
            skipped.append(account_id)
            skipped_details.append({"account_id": account_id, "reason": "actor could not be resolved"})
            continue
        synced.append(_serialize_user_summary(user))

    return {
        "ok": True,
        "channel": channel,
        "synced_count": len(synced),
        "skipped_count": len(skipped),
        "synced_users": synced,
        "skipped_account_ids": skipped,
        "skipped_accounts": skipped_details,
    }


@router.post("/users/{user_id}/disable")
def user_disable(
    user_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    actor_user_id = actor.id
    try:
        user = disable_user(db, user_id=user_id, actor_user_id=actor_user_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"ok": True, "user": {"id": user.id, "status": user.status}}


@router.post("/knowledge/{document_id}/permissions")
def knowledge_grant_permission(
    document_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    user_id = str(payload.get("user_id") or "").strip()
    access_level = str(payload.get("access_level") or "read").strip()
    if access_level not in {"read", "write", "owner"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="access_level must be read, write, or owner")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    if db.get(KnowledgeDocument, document_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge document not found")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    actor_user_id = actor.id
    permission = grant_document_permission(db, document_id=document_id, user_id=user_id, actor_user_id=actor_user_id, access_level=access_level)
    return {
        "ok": True,
        "permission": {
            "id": permission.id,
            "document_id": permission.document_id,
            "user_id": permission.user_id,
            "access_level": permission.access_level,
        },
    }


@router.post("/knowledge/batch-permissions")
def knowledge_batch_grant_permission(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    user_id = str(payload.get("user_id") or "").strip()
    document_ids = payload.get("document_ids")
    if not user_id or not isinstance(document_ids, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id and document_ids are required")
    permissions = batch_grant_documents(db, document_ids=[str(item) for item in document_ids], user_id=user_id)
    return {"ok": True, "granted_count": len(permissions)}


@router.post("/source-files/{source_file_id}/permissions")
def source_file_grant_permission(
    source_file_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    if db.get(KnowledgeSourceFile, source_file_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source file not found")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    permission = grant_source_file_permission(db, source_file_id=source_file_id, user_id=user_id)
    return {"ok": True, "permission": {"id": permission.id, "source_file_id": permission.source_file_id, "user_id": permission.user_id}}


@router.get("/source-files/{source_file_id}/download")
def source_file_download(
    source_file_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_actor),
) -> FileResponse:
    source_file = db.get(KnowledgeSourceFile, source_file_id)
    if source_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source file not found")
    if not can_access_source_file(db, actor, source_file):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="source file permission required")

    source_path = _resolve_source_file_path(source_file.file_path)
    if not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source file missing on disk")
    return FileResponse(
        source_path,
        media_type=source_file.mime_type or "application/octet-stream",
        filename=source_file.file_name,
    )


def _resolve_source_file_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@router.post("/knowledge/groups")
def knowledge_create_group(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    group = create_document_group(db, name=name, created_by=actor.id, description=str(payload.get("description") or "") or None)
    return {"ok": True, "group": {"id": group.id, "name": group.name}}


@router.post("/knowledge/groups/{group_id}/documents")
def knowledge_add_group_document(
    group_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    document_id = str(payload.get("document_id") or "").strip()
    if not document_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="document_id is required")
    membership = add_document_to_group(db, group_id=group_id, document_id=document_id)
    return {"ok": True, "membership": {"id": membership.id, "group_id": membership.group_id, "document_id": membership.document_id}}


@router.post("/projects/{project_id}/knowledge-permissions")
def project_grant_knowledge_permission(
    project_id: str,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    actor: User = Depends(get_management_actor),
) -> dict[str, object]:
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    permission = grant_project_permission(db, project_id=project_id, user_id=user_id)
    return {"ok": True, "permission": {"id": permission.id, "project_id": permission.project_id, "user_id": permission.user_id}}


@router.post("/support/unanswered/{unanswered_id}/status")
def support_update_unanswered_status(unanswered_id: str, payload: dict[str, object], db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return update_unanswered_question_status(db, unanswered_id, status=str(payload.get("status") or "pending"))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
