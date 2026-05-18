from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    ConfirmationAction,
    Customer,
    KnowledgeDocument,
    KnowledgeDocumentGroup,
    KnowledgeDocumentPermission,
    KnowledgeProjectPermission,
    KnowledgeSourceFile,
    KnowledgeSourceFilePermission,
    Project,
    ProjectEvent,
    ProjectTask,
    SupportUnansweredQuestion,
    User,
    UserChannelBinding,
)
from app.services.knowledge_service import batch_grant_documents

SAFE_USER_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")


def grant_document_permission(
    db: Session,
    *,
    document_id: str,
    user_id: str,
    actor_user_id: str,
    access_level: str = "read",
) -> KnowledgeDocumentPermission:
    permission = batch_grant_documents(db, document_ids=[document_id], user_id=user_id, access_level=access_level)[0]
    _write_permission_audit(
        db,
        actor_user_id=actor_user_id,
        action="grant_document_permission",
        target_type="knowledge_document",
        target_id=document_id,
        summary=f"Granted {access_level} access to {user_id}",
    )
    return permission


def disable_user(db: Session, *, user_id: str, actor_user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("user not found")
    user.status = "disabled"
    db.commit()
    db.refresh(user)
    _write_permission_audit(
        db,
        actor_user_id=actor_user_id,
        action="disable_user",
        target_type="user",
        target_id=user.id,
        summary=f"Disabled user {user.id}",
    )
    return user


def sync_channel_account_alias(
    db: Session,
    *,
    channel: str,
    account_id: str,
    alias_user_id: str,
) -> User:
    account_id = account_id.strip()
    alias_user_id = alias_user_id.strip()
    _validate_alias_user_id(alias_user_id)
    if not account_id:
        raise ValueError("account_id is required")

    existing_binding = (
        db.query(UserChannelBinding)
        .filter(UserChannelBinding.channel == channel, UserChannelBinding.external_user_id == account_id)
        .one_or_none()
    )
    existing_alias_user = db.get(User, alias_user_id)
    old_user = db.get(User, existing_binding.user_id) if existing_binding is not None else db.get(User, account_id)

    if existing_alias_user is not None:
        if existing_alias_user.status != "active":
            raise ValueError("alias user is disabled")
        if old_user is not None and old_user.id != existing_alias_user.id:
            _move_user_references(db, old_user.id, existing_alias_user.id)
            db.delete(old_user)
        user = existing_alias_user
    elif old_user is not None:
        old_user_id = old_user.id
        old_user.id = alias_user_id
        old_user.name = f"{channel}:{alias_user_id}"
        _move_user_references(db, old_user_id, alias_user_id)
        user = old_user
    else:
        user = User(id=alias_user_id, name=f"{channel}:{alias_user_id}", role="member", status="active", knowledge_access_policy="own")
        db.add(user)

    db.flush()
    if existing_binding is None:
        db.add(UserChannelBinding(user_id=user.id, channel=channel, external_user_id=account_id))
    else:
        existing_binding.user_id = user.id
    db.commit()
    db.refresh(user)
    return user


def _validate_alias_user_id(user_id: str) -> None:
    if not user_id:
        raise ValueError("user_id is required")
    if len(user_id) > 36 or len(user_id) < 2 or any(char not in SAFE_USER_ID_CHARS for char in user_id):
        raise ValueError("user_id must be 2-36 characters and only contain letters, numbers, underscore, dot, or hyphen")


def _move_user_references(db: Session, old_user_id: str, new_user_id: str) -> None:
    if old_user_id == new_user_id:
        return
    _delete_duplicate_permissions_before_merge(db, old_user_id, new_user_id)
    for model, column_name in (
        (AuditLog, "user_id"),
        (ConfirmationAction, "actor_user_id"),
        (Customer, "owner_user_id"),
        (KnowledgeDocument, "created_by"),
        (KnowledgeDocumentGroup, "created_by"),
        (KnowledgeDocumentPermission, "user_id"),
        (KnowledgeProjectPermission, "user_id"),
        (KnowledgeSourceFile, "uploaded_by"),
        (KnowledgeSourceFilePermission, "user_id"),
        (Project, "owner_user_id"),
        (ProjectEvent, "created_by"),
        (ProjectTask, "owner_user_id"),
        (ProjectTask, "created_by"),
        (SupportUnansweredQuestion, "user_id"),
        (UserChannelBinding, "user_id"),
    ):
        db.query(model).filter(getattr(model, column_name) == old_user_id).update({column_name: new_user_id}, synchronize_session=False)


def _delete_duplicate_permissions_before_merge(db: Session, old_user_id: str, new_user_id: str) -> None:
    old_document_permissions = db.query(KnowledgeDocumentPermission).filter(KnowledgeDocumentPermission.user_id == old_user_id).all()
    for permission in old_document_permissions:
        duplicate = (
            db.query(KnowledgeDocumentPermission)
            .filter(
                KnowledgeDocumentPermission.document_id == permission.document_id,
                KnowledgeDocumentPermission.user_id == new_user_id,
            )
            .one_or_none()
        )
        if duplicate is not None:
            db.delete(permission)

    old_source_file_permissions = db.query(KnowledgeSourceFilePermission).filter(KnowledgeSourceFilePermission.user_id == old_user_id).all()
    for permission in old_source_file_permissions:
        duplicate = (
            db.query(KnowledgeSourceFilePermission)
            .filter(
                KnowledgeSourceFilePermission.source_file_id == permission.source_file_id,
                KnowledgeSourceFilePermission.user_id == new_user_id,
            )
            .one_or_none()
        )
        if duplicate is not None:
            db.delete(permission)
    db.flush()


def _write_permission_audit(
    db: Session,
    *,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    summary: str,
) -> None:
    audit = AuditLog(
        user_id=actor_user_id,
        channel="web",
        action=action,
        tool_name="knowledge_permission_grant" if action.endswith("permission") else action,
        response_summary=summary,
        target_type=target_type,
        target_id=target_id,
    )
    audit.request_payload = {"action": action, "target_type": target_type, "target_id": target_id}
    db.add(audit)
    db.commit()
