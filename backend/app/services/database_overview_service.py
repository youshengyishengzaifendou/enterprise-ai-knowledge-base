from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.industry_config import get_industry_config, serialize_industry_config
from app.models import (
    AuditLog,
    ConfirmationAction,
    Customer,
    KnowledgeChunk,
    KnowledgeConflictReport,
    KnowledgeDocument,
    KnowledgeDocumentPermission,
    KnowledgeDocumentVersion,
    KnowledgeSourceFile,
    KnowledgeSourceFilePermission,
    KnowledgeDocumentGroup,
    KnowledgeDocumentGroupMembership,
    KnowledgeProjectPermission,
    Project,
    ProjectEvent,
    ProjectRisk,
    ProjectTask,
    SupportUnansweredQuestion,
    User,
    UserChannelBinding,
)

CUSTOMER_NAME_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,40}(?:集团|公司|银行|证券|保险|大学|医院|政府|委员会))")
CUSTOMER_NAME_PREFIXES = ("记录", "查询", "关于", "客户", "标题", "去", "到", "拜访", "对接", "联系", "前往", "访问")


@dataclass(frozen=True)
class TableOverviewConfig:
    id: str
    label: str
    model: type
    columns: tuple[str, ...]
    order_by: str


TABLES: tuple[TableOverviewConfig, ...] = (
    TableOverviewConfig(
        id="users",
        label="用户",
        model=User,
        columns=("id", "name", "email", "role", "knowledge_access_policy", "status", "created_at", "updated_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="user_channel_bindings",
        label="用户渠道绑定",
        model=UserChannelBinding,
        columns=("id", "user_id", "channel", "external_user_id", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="knowledge_document_permissions",
        label="知识文档授权",
        model=KnowledgeDocumentPermission,
        columns=("id", "document_id", "user_id", "access_level", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="knowledge_source_files",
        label="原文档",
        model=KnowledgeSourceFile,
        columns=(
            "id",
            "file_name",
            "file_path",
            "storage",
            "mime_type",
            "file_size",
            "uploaded_by",
            "source_channel",
            "source_external_user_id",
            "parse_status",
            "parse_error",
            "linked_document_id",
            "created_at",
            "updated_at",
        ),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="knowledge_source_file_permissions",
        label="原文档授权",
        model=KnowledgeSourceFilePermission,
        columns=("id", "source_file_id", "user_id", "access_level", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="knowledge_document_groups",
        label="文档分组",
        model=KnowledgeDocumentGroup,
        columns=("id", "name", "description", "created_by", "created_at", "updated_at"),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="knowledge_document_group_memberships",
        label="分组文档",
        model=KnowledgeDocumentGroupMembership,
        columns=("id", "group_id", "document_id", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="knowledge_project_permissions",
        label="项目知识权限",
        model=KnowledgeProjectPermission,
        columns=("id", "project_id", "user_id", "access_level", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="customers",
        label="客户",
        model=Customer,
        columns=(
            "id",
            "name",
            "aliases",
            "industry",
            "level",
            "status",
            "owner_user_id",
            "contact_name",
            "contact_phone",
            "contact_email",
            "created_at",
            "updated_at",
        ),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="projects",
        label="项目",
        model=Project,
        columns=(
            "id",
            "customer_id",
            "name",
            "aliases",
            "stage",
            "status",
            "amount",
            "owner_user_id",
            "expected_sign_date",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="project_events",
        label="项目进展",
        model=ProjectEvent,
        columns=(
            "id",
            "project_id",
            "customer_id",
            "event_type",
            "title",
            "summary",
            "detail",
            "source_type",
            "source_url",
            "created_by",
            "event_time",
            "created_at",
        ),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="project_tasks",
        label="项目任务",
        model=ProjectTask,
        columns=(
            "id",
            "project_id",
            "customer_id",
            "title",
            "description",
            "owner_user_id",
            "status",
            "due_date",
            "created_by",
            "created_at",
            "updated_at",
        ),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="project_risks",
        label="项目风险",
        model=ProjectRisk,
        columns=(
            "id",
            "project_id",
            "customer_id",
            "risk_title",
            "risk_detail",
            "risk_level",
            "status",
            "owner_user_id",
            "mitigation_plan",
            "due_date",
            "created_at",
            "updated_at",
        ),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="knowledge_documents",
        label="知识文档",
        model=KnowledgeDocument,
        columns=(
            "id",
            "title",
            "source_type",
            "source_url",
            "source_file_name",
            "source_file_path",
            "source_file_storage",
            "source_file_mime_type",
            "source_file_size",
            "source_file_id",
            "source_channel",
            "source_external_user_id",
            "parse_status",
            "parse_error",
            "index_status",
            "review_status",
            "publication_status",
            "current_version",
            "reviewed_by",
            "reviewed_at",
            "customer_id",
            "project_id",
            "summary",
            "content_text",
            "created_by",
            "created_at",
            "updated_at",
        ),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="knowledge_document_versions",
        label="知识版本",
        model=KnowledgeDocumentVersion,
        columns=("id", "document_id", "version_number", "title", "summary", "content_text", "source_file_id", "created_by", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="knowledge_conflict_reports",
        label="知识冲突",
        model=KnowledgeConflictReport,
        columns=("id", "document_id", "related_document_id", "conflict_type", "detail", "status", "created_at", "updated_at"),
        order_by="updated_at",
    ),
    TableOverviewConfig(
        id="knowledge_chunks",
        label="知识切片",
        model=KnowledgeChunk,
        columns=("id", "document_id", "chunk_index", "content_text", "embedding_model", "index_status", "token_count", "indexed_at", "created_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="confirmation_actions",
        label="确认动作",
        model=ConfirmationAction,
        columns=("id", "actor_user_id", "action", "status", "summary", "payload", "expires_at", "created_at", "completed_at"),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="audit_logs",
        label="审计日志",
        model=AuditLog,
        columns=(
            "id",
            "user_id",
            "channel",
            "action",
            "tool_name",
            "request_payload",
            "response_summary",
            "target_type",
            "target_id",
            "created_at",
        ),
        order_by="created_at",
    ),
    TableOverviewConfig(
        id="support_unanswered_questions",
        label="无答案问题",
        model=SupportUnansweredQuestion,
        columns=("id", "question", "customer_id", "project_id", "user_id", "status", "source", "created_at", "updated_at"),
        order_by="created_at",
    ),
)


def get_database_overview(db: Session, *, limit: int = 25, industry_key: str | None = None) -> dict[str, Any]:
    industry = get_industry_config(industry_key)
    return {
        "ok": True,
        "industry": serialize_industry_config(industry),
        "title": industry.title,
        "description": industry.description,
        "labels": industry.labels,
        "tables": [_build_table_overview(db, config, limit, industry.table_labels.get(config.id)) for config in TABLES],
    }


def get_customer_related_info(db: Session, customer_name: str, *, limit: int = 25, industry_key: str | None = None) -> dict[str, Any]:
    industry = get_industry_config(industry_key)
    normalized_name = customer_name.strip()
    customer = db.scalar(select(Customer).where(Customer.name == normalized_name))
    customer_id = customer.id if customer else None

    document_conditions = [
        KnowledgeDocument.title.contains(normalized_name),
        KnowledgeDocument.summary.contains(normalized_name),
        KnowledgeDocument.content_text.contains(normalized_name),
    ]
    if customer_id:
        document_conditions.append(KnowledgeDocument.customer_id == customer_id)

    documents = db.scalars(
        select(KnowledgeDocument)
        .where(or_(*document_conditions))
        .order_by(KnowledgeDocument.updated_at.desc())
        .limit(limit)
    ).all()
    document_ids = [document.id for document in documents]

    chunk_conditions = [KnowledgeChunk.content_text.contains(normalized_name)]
    if document_ids:
        chunk_conditions.append(KnowledgeChunk.document_id.in_(document_ids))
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(or_(*chunk_conditions))
        .order_by(KnowledgeChunk.created_at.desc())
        .limit(limit)
    ).all()

    similar_case_conditions = [
        Project.name.contains(normalized_name),
        Project.aliases_json.contains(normalized_name),
    ]
    if customer_id:
        similar_case_conditions.append(Project.customer_id == customer_id)
    for document in documents:
        if document.project_id:
            similar_case_conditions.append(Project.id == document.project_id)
    similar_cases = db.scalars(
        select(Project)
        .where(or_(*similar_case_conditions))
        .order_by(Project.updated_at.desc())
        .limit(limit)
    ).all()

    audit_conditions = [
        AuditLog.request_payload_json.contains(normalized_name),
        AuditLog.response_summary.contains(normalized_name),
    ]
    if customer_id:
        audit_conditions.append(AuditLog.target_id == customer_id)
    if document_ids:
        audit_conditions.append(AuditLog.target_id.in_(document_ids))
    audit_logs = db.scalars(
        select(AuditLog)
        .where(or_(*audit_conditions))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()

    return {
        "ok": True,
        "customer_name": normalized_name,
        "industry": serialize_industry_config(industry),
        "labels": industry.related_labels,
        "documents": [_with_table_id(_serialize_row(document, _table_columns("knowledge_documents")), "knowledge_documents") for document in documents],
        "chunks": [_with_table_id(_serialize_row(chunk, _table_columns("knowledge_chunks")), "knowledge_chunks") for chunk in chunks],
        "similar_cases": [_with_table_id(_serialize_row(project, _table_columns("projects")), "projects") for project in similar_cases],
        "audit_logs": [_with_table_id(_serialize_row(log, _table_columns("audit_logs")), "audit_logs") for log in audit_logs],
    }


def _build_table_overview(db: Session, config: TableOverviewConfig, limit: int, label_override: str | None = None) -> dict[str, Any]:
    rows = [_serialize_row(row, config.columns) for row in _recent_rows(db, config, limit)]
    count = _count_rows(db, config.model)
    columns = list(config.columns)

    if config.id == "customers":
        inferred_rows = _infer_customer_rows_from_knowledge(db, rows, limit)
        if inferred_rows:
            columns = [*columns, "source", "knowledge_document_count"]
            rows = [*rows, *inferred_rows]
            count += len(inferred_rows)

    return {
        "id": config.id,
        "label": label_override or config.label,
        "count": count,
        "columns": columns,
        "rows": rows,
    }


def _count_rows(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _recent_rows(db: Session, config: TableOverviewConfig, limit: int) -> Iterable[Any]:
    order_column = getattr(config.model, config.order_by)
    return db.scalars(select(config.model).order_by(order_column.desc()).limit(limit)).all()


def _serialize_row(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    return {column: _json_safe(getattr(row, column)) for column in columns}


def _table_columns(table_id: str) -> tuple[str, ...]:
    for config in TABLES:
        if config.id == table_id:
            return config.columns
    raise ValueError(f"Unknown table id: {table_id}")


def _with_table_id(row: dict[str, Any], table_id: str) -> dict[str, Any]:
    return {**row, "table_id": table_id}


def _infer_customer_rows_from_knowledge(db: Session, existing_customer_rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    existing_names = {str(row.get("name")) for row in existing_customer_rows if row.get("name")}
    documents = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())).all()
    customer_hits: dict[str, dict[str, Any]] = {}

    for document in documents:
        text = "\n".join(value for value in (document.title, document.summary, document.content_text[:500]) if value)
        for customer_name in _extract_customer_names(text):
            if customer_name in existing_names:
                continue
            hit = customer_hits.setdefault(
                customer_name,
                {
                    "id": f"inferred-customer-{customer_name}",
                    "name": customer_name,
                    "aliases": [],
                    "industry": None,
                    "level": None,
                    "status": "inferred",
                    "owner_user_id": None,
                    "contact_name": None,
                    "contact_phone": None,
                    "contact_email": None,
                    "created_at": _json_safe(document.created_at),
                    "updated_at": _json_safe(document.updated_at),
                    "source": "知识库推断",
                    "knowledge_document_count": 0,
                },
            )
            hit["knowledge_document_count"] += 1
            if document.updated_at and str(document.updated_at.isoformat()) > str(hit["updated_at"] or ""):
                hit["updated_at"] = _json_safe(document.updated_at)

    return sorted(customer_hits.values(), key=lambda row: str(row.get("updated_at") or ""), reverse=True)[:limit]


def _extract_customer_names(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for match in CUSTOMER_NAME_PATTERN.findall(text):
        name = _clean_customer_name(match)
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    return names


def _clean_customer_name(name: str) -> str:
    cleaned = name.strip(" ，。；：:、\n\t")
    for prefix in CUSTOMER_NAME_PREFIXES:
        if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 1:
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list | dict) or value is None:
        return value
    return value
