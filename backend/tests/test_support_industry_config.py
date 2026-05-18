from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AuditLog, Customer, KnowledgeChunk, KnowledgeConflictReport, KnowledgeDocument, KnowledgeDocumentVersion, KnowledgeSourceFile, Project
from app.services.database_overview_service import get_customer_related_info, get_database_overview


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_support_industry_labels_and_aliases_are_returned():
    db = make_session()

    overview = get_database_overview(db, industry_key="support")

    assert overview["industry"]["key"] == "support"
    assert overview["title"] == "客服知识库看板"
    assert overview["labels"]["customer"] == "客户/用户/账号"
    assert overview["labels"]["project"] == "问题/工单"
    assert table_label(overview, "projects") == "问题/工单"
    assert table_label(overview, "knowledge_documents") == "知识文章"
    assert table_label(overview, "knowledge_chunks") == "答案片段"
    assert table_label(overview, "audit_logs") == "查询/写入/回复建议记录"


def test_default_industry_keeps_enterprise_labels():
    db = make_session()

    overview = get_database_overview(db)

    assert overview["industry"]["key"] == "enterprise"
    assert overview["title"] == "数据库记录看板"
    assert table_label(overview, "projects") == "项目"
    assert table_label(overview, "knowledge_documents") == "知识文档"


def test_database_overview_exposes_knowledge_operations_tables_and_columns():
    db = make_session()
    document = KnowledgeDocument(
        id="doc-1",
        title="版本知识",
        source_type="manual",
        content_text="版本内容",
        created_by="user-1",
        review_status="approved",
        publication_status="published",
        current_version=2,
    )
    source_file = KnowledgeSourceFile(
        id="file-1",
        file_name="原文档.pdf",
        file_path="/tmp/source.pdf",
        uploaded_by="user-1",
        parse_status="parsed",
        linked_document_id="doc-1",
    )
    version = KnowledgeDocumentVersion(
        id="version-1",
        document_id="doc-1",
        version_number=2,
        title="版本知识",
        content_text="版本内容",
        source_file_id="file-1",
        created_by="admin",
    )
    conflict = KnowledgeConflictReport(
        id="conflict-1",
        document_id="doc-1",
        related_document_id="doc-1",
        detail="可能冲突",
    )
    db.add_all([document, source_file, version, conflict])
    db.commit()

    overview = get_database_overview(db)
    knowledge_table = table_by_id(overview, "knowledge_documents")
    source_file_table = table_by_id(overview, "knowledge_source_files")
    version_table = table_by_id(overview, "knowledge_document_versions")
    conflict_table = table_by_id(overview, "knowledge_conflict_reports")

    assert "review_status" in knowledge_table["columns"]
    assert "publication_status" in knowledge_table["columns"]
    assert "current_version" in knowledge_table["columns"]
    assert "parse_status" in source_file_table["columns"]
    assert "linked_document_id" in source_file_table["columns"]
    assert version_table["rows"][0]["version_number"] == 2
    assert conflict_table["rows"][0]["status"] == "open"


def test_support_customer_related_info_includes_support_sections():
    db = make_session()
    customer = Customer(id="customer-1", name="中信集团", industry="金融", status="active")
    project = Project(id="case-1", customer_id="customer-1", name="登录失败工单", stage="处理中", status="active")
    document = KnowledgeDocument(
        id="doc-1",
        title="中信集团登录问题处理标准",
        source_type="manual",
        customer_id="customer-1",
        project_id="case-1",
        summary="登录失败时先核验账号状态。",
        content_text="中信集团用户登录失败时，客服坐席先核验账号状态，再重置密码。",
        created_by="user-1",
    )
    chunk = KnowledgeChunk(id="chunk-1", document_id="doc-1", chunk_index=0, content_text="账号登录失败标准答案：核验账号状态，重置密码。")
    audit = AuditLog(
        id="audit-1",
        channel="openclaw",
        action="kb_answer",
        tool_name="kb_answer",
        response_summary="已根据中信集团登录问题生成建议回复。",
        target_type="knowledge_document",
        target_id="doc-1",
    )
    audit.request_payload = {"query": "中信集团登录失败怎么回复"}
    db.add_all([customer, project, document, chunk, audit])
    db.commit()

    related = get_customer_related_info(db, "中信集团", industry_key="support")

    assert related["labels"]["documents"] == "相关知识文章"
    assert related["labels"]["chunks"] == "相关答案片段"
    assert related["labels"]["similar_cases"] == "历史相似问题"
    assert related["labels"]["audit_logs"] == "最近查询/写入记录"
    assert related["documents"][0]["id"] == "doc-1"
    assert related["chunks"][0]["id"] == "chunk-1"
    assert related["similar_cases"][0]["id"] == "case-1"
    assert related["audit_logs"][0]["id"] == "audit-1"


def table_label(overview: dict, table_id: str) -> str:
    return next(table["label"] for table in overview["tables"] if table["id"] == table_id)


def table_by_id(overview: dict, table_id: str) -> dict:
    return next(table for table in overview["tables"] if table["id"] == table_id)
