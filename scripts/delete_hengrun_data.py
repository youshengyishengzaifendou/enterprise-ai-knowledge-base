from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    ConfirmationAction,
    Customer,
    KnowledgeChunk,
    KnowledgeDocument,
    Project,
    ProjectEvent,
    ProjectRisk,
    ProjectTask,
)


DATABASE_URL = "sqlite:///./enterprise_ai_assistant.db"
CUSTOMER_ID = "customer-demo"
PROJECT_ID = "project-demo"


def main() -> None:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    with Session(engine) as db:
        document_ids = set(
            db.scalars(
                select(KnowledgeDocument.id).where(
                    or_(
                        KnowledgeDocument.customer_id == CUSTOMER_ID,
                        KnowledgeDocument.project_id == PROJECT_ID,
                        KnowledgeDocument.title.contains("恒润"),
                        KnowledgeDocument.summary.contains("恒润"),
                        KnowledgeDocument.content_text.contains("恒润"),
                    )
                )
            ).all()
        )

        counts = {
            "knowledge_chunks": _delete_chunks(db, document_ids),
            "knowledge_documents": _delete_documents(db, document_ids),
            "project_events": _delete_by_customer_or_project(db, ProjectEvent),
            "project_tasks": _delete_by_customer_or_project(db, ProjectTask),
            "project_risks": _delete_by_customer_or_project(db, ProjectRisk),
            "confirmation_actions": _delete_confirmations(db),
            "audit_logs": _delete_audit_logs(db, document_ids),
            "projects": _delete_projects(db),
            "customers": _delete_customers(db),
        }
        db.commit()

    for table, count in counts.items():
        print(f"{table}: {count}")


def _delete_chunks(db: Session, document_ids: set[str]) -> int:
    if not document_ids:
        return 0
    result = db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id.in_(document_ids)))
    return int(result.rowcount or 0)


def _delete_documents(db: Session, document_ids: set[str]) -> int:
    if not document_ids:
        return 0
    result = db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))
    return int(result.rowcount or 0)


def _delete_by_customer_or_project(db: Session, model: type[ProjectEvent | ProjectTask | ProjectRisk]) -> int:
    result = db.execute(delete(model).where(or_(model.customer_id == CUSTOMER_ID, model.project_id == PROJECT_ID)))
    return int(result.rowcount or 0)


def _delete_confirmations(db: Session) -> int:
    result = db.execute(
        delete(ConfirmationAction).where(
            or_(
                ConfirmationAction.payload_json.contains("恒润"),
                ConfirmationAction.payload_json.contains(CUSTOMER_ID),
                ConfirmationAction.payload_json.contains(PROJECT_ID),
                ConfirmationAction.summary.contains("恒润"),
            )
        )
    )
    return int(result.rowcount or 0)


def _delete_audit_logs(db: Session, document_ids: set[str]) -> int:
    conditions = [
        AuditLog.request_payload_json.contains("恒润"),
        AuditLog.request_payload_json.contains(CUSTOMER_ID),
        AuditLog.request_payload_json.contains(PROJECT_ID),
        AuditLog.response_summary.contains("恒润"),
        AuditLog.target_id == CUSTOMER_ID,
        AuditLog.target_id == PROJECT_ID,
    ]
    if document_ids:
        conditions.append(AuditLog.target_id.in_(document_ids))
    result = db.execute(delete(AuditLog).where(or_(*conditions)))
    return int(result.rowcount or 0)


def _delete_projects(db: Session) -> int:
    result = db.execute(delete(Project).where(or_(Project.id == PROJECT_ID, Project.customer_id == CUSTOMER_ID, Project.name.contains("恒润"))))
    return int(result.rowcount or 0)


def _delete_customers(db: Session) -> int:
    result = db.execute(delete(Customer).where(or_(Customer.id == CUSTOMER_ID, Customer.name.contains("恒润"), Customer.aliases_json.contains("恒润"))))
    return int(result.rowcount or 0)


if __name__ == "__main__":
    main()
