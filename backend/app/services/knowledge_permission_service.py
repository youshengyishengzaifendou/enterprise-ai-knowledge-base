from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    KnowledgeDocument,
    KnowledgeDocumentPermission,
    KnowledgeProjectPermission,
    KnowledgeSourceFile,
    KnowledgeSourceFilePermission,
    Project,
    User,
)
from app.services.permission_service import can_access_customer, can_access_project


def can_access_document(db: Session, user: User | None, document: KnowledgeDocument) -> bool:
    if user is None:
        return True
    if user.role == "admin" or user.knowledge_access_policy == "all":
        return True
    if document.created_by == user.id:
        return True
    if _has_document_permission(db, user.id, document.id):
        return True
    if document.project_id:
        return _can_access_project_document(db, user, document.project_id)
    if document.customer_id:
        customer = db.get(Customer, document.customer_id)
        return customer is not None and can_access_customer(db, user, customer)
    return False


def can_access_source_file(db: Session, user: User | None, source_file: KnowledgeSourceFile) -> bool:
    if user is None:
        return True
    if user.role == "admin" or user.knowledge_access_policy == "all":
        return True
    if source_file.uploaded_by == user.id:
        return True
    permission = db.scalar(
        select(KnowledgeSourceFilePermission).where(
            KnowledgeSourceFilePermission.source_file_id == source_file.id,
            KnowledgeSourceFilePermission.user_id == user.id,
            KnowledgeSourceFilePermission.access_level.in_(("read", "write", "owner")),
        )
    )
    return permission is not None


def _has_document_permission(db: Session, user_id: str, document_id: str) -> bool:
    permission = db.scalar(
        select(KnowledgeDocumentPermission).where(
            KnowledgeDocumentPermission.document_id == document_id,
            KnowledgeDocumentPermission.user_id == user_id,
            KnowledgeDocumentPermission.access_level.in_(("read", "write", "owner")),
        )
    )
    return permission is not None


def _can_access_project_document(db: Session, user: User, project_id: str) -> bool:
    project = db.get(Project, project_id)
    project_permission = db.scalar(
        select(KnowledgeProjectPermission).where(
            KnowledgeProjectPermission.project_id == project_id,
            KnowledgeProjectPermission.user_id == user.id,
            KnowledgeProjectPermission.access_level.in_(("read", "write", "owner")),
        )
    )
    return project_permission is not None or (project is not None and can_access_project(db, user, project))
