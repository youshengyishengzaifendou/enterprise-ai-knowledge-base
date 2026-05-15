from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from openpyxl import Workbook
from docx import Document

from app.db.base import Base
from app.models import AuditLog, KnowledgeDocument, User
from app.services.knowledge_service import answer_with_knowledge, find_source_files, ingest_document
from app.services.support_operations_service import (
    get_support_operations_dashboard,
    import_knowledge_file,
    import_faq_text,
    list_unanswered_questions,
    update_unanswered_question_status,
)


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_unanswered_question_is_captured_when_answer_has_no_match():
    db = make_session()

    result = answer_with_knowledge(db, query="发票抬头写错了怎么处理", user=None, actor_user_id="agent-1")

    unanswered = list_unanswered_questions(db)
    assert result["answer"].startswith("没有找到可用的知识库内容")
    assert len(unanswered) == 1
    assert unanswered[0]["question"] == "发票抬头写错了怎么处理"
    assert unanswered[0]["status"] == "pending"


def test_dashboard_reports_knowledge_operations_metrics():
    db = make_session()
    user = User(id="agent-1", name="客服A", role="member", status="active")
    document = KnowledgeDocument(
        id="doc-1",
        title="退款政策",
        source_type="manual",
        summary="退款处理规则",
        content_text="订单未发货可以直接退款，已发货需先拒收或退回。",
        created_by="agent-1",
    )
    log_hit = AuditLog(id="audit-hit", user_id="agent-1", channel="openclaw", action="query", tool_name="kb_answer", response_summary="已根据知识库生成回答。")
    log_hit.request_payload = {"input": {"query": "订单未发货怎么退款"}}
    log_miss = AuditLog(id="audit-miss", user_id="agent-1", channel="openclaw", action="query", tool_name="kb_answer", response_summary="没有找到可用的知识库内容。")
    log_miss.request_payload = {"input": {"query": "发票抬头写错了怎么办"}}
    db.add_all([user, document, log_hit, log_miss])
    db.commit()
    answer_with_knowledge(db, query="发票抬头写错了怎么办", user=None, actor_user_id="agent-1")

    dashboard = get_support_operations_dashboard(db)

    assert dashboard["metrics"]["knowledge_documents"] == 1
    assert dashboard["metrics"]["total_queries"] == 2
    assert dashboard["metrics"]["hit_queries"] == 1
    assert dashboard["metrics"]["missed_queries"] == 1
    assert dashboard["metrics"]["unanswered_questions"] == 1
    assert dashboard["popular_questions"][0]["question"] == "订单未发货怎么退款"


def test_import_faq_text_creates_support_knowledge_documents():
    db = make_session()

    result = import_faq_text(
        db,
        text="问题,答案\n怎么退款,订单未发货可以直接退款\n物流丢件怎么办,先联系快递核实并补发",
        user_id="agent-1",
        source_type="faq_csv",
    )

    assert result["imported_count"] == 2
    documents = db.query(KnowledgeDocument).order_by(KnowledgeDocument.title.asc()).all()
    assert [document.title for document in documents] == ["怎么退款", "物流丢件怎么办"]
    assert documents[0].source_type == "faq_csv"


def test_ingest_document_preserves_source_file_index():
    db = make_session()

    document = ingest_document(
        db,
        payload={
            "title": "邮件安全升级手册",
            "content_text": "升级前需要备份配置，并在维护窗口执行升级。",
            "source_file_path": "/root/.openclaw/media/inbound/邮件安全升级手册.pdf",
            "source_file_name": "邮件安全升级手册.pdf",
            "source_file_mime_type": "application/pdf",
            "source_file_size": 2048,
            "source_file_storage": "openclaw_media",
        },
        user_id="agent-1",
    )

    saved = db.get(KnowledgeDocument, document.id)
    assert saved is not None
    assert saved.source_file_path == "/root/.openclaw/media/inbound/邮件安全升级手册.pdf"
    assert saved.source_file_name == "邮件安全升级手册.pdf"
    assert saved.source_file_mime_type == "application/pdf"
    assert saved.source_file_size == 2048
    assert saved.source_file_storage == "openclaw_media"


def test_find_source_files_matches_filename_and_document_title():
    db = make_session()
    ingest_document(
        db,
        payload={
            "title": "退换货政策原文",
            "content_text": "七天无理由退货需要商品不影响二次销售。",
            "project_id": "project-demo",
            "source_file_path": "/root/.openclaw/media/inbound/售后政策.docx",
            "source_file_name": "售后政策.docx",
            "source_file_storage": "openclaw_media",
        },
        user_id="agent-1",
    )

    by_file = find_source_files(db, query="售后政策", project_id="project-demo")
    by_title = find_source_files(db, query="退换货", project_id="project-demo")

    assert by_file[0]["source_file_name"] == "售后政策.docx"
    assert by_file[0]["source_file_path"] == "/root/.openclaw/media/inbound/售后政策.docx"
    assert by_file[0]["document_title"] == "退换货政策原文"
    assert by_title[0]["source_file_storage"] == "openclaw_media"


def test_unanswered_question_status_can_be_resolved_or_ignored():
    db = make_session()
    answer_with_knowledge(db, query="会员生日券能不能叠加满减", user=None, actor_user_id="agent-1")
    unanswered = list_unanswered_questions(db)[0]

    updated = update_unanswered_question_status(db, unanswered["id"], status="resolved")

    assert updated["status"] == "resolved"
    assert list_unanswered_questions(db, status="pending") == []
    assert list_unanswered_questions(db, status="resolved")[0]["question"] == "会员生日券能不能叠加满减"


def test_import_markdown_and_plain_text_documents():
    db = make_session()

    markdown_result = import_faq_text(
        db,
        text="# 退货政策\n\n客户收到商品七天内可以申请无理由退货，特殊商品除外。",
        user_id="agent-1",
        source_type="markdown",
    )
    text_result = import_faq_text(
        db,
        text="物流异常处理\n客户反馈物流停滞超过48小时，客服需要联系快递核实并同步客户。",
        user_id="agent-1",
        source_type="txt",
    )

    assert markdown_result["imported_count"] == 1
    assert text_result["imported_count"] == 1
    titles = [document.title for document in db.query(KnowledgeDocument).order_by(KnowledgeDocument.title.asc()).all()]
    assert titles == ["物流异常处理", "退货政策"]


def test_import_knowledge_file_preserves_original_file_index(tmp_path):
    db = make_session()
    source = tmp_path / "退货说明.txt"
    source.write_text("退货说明\n客户收到商品七天内可以申请退货。", encoding="utf-8")

    result = import_knowledge_file(
        db,
        filename=source.name,
        content=source.read_bytes(),
        user_id="agent-1",
        source_type="txt",
    )

    assert result["imported_count"] == 1
    document = db.query(KnowledgeDocument).one()
    assert document.title == "退货说明"
    assert document.source_file_name == "退货说明.txt"
    assert document.source_file_path is not None
    assert document.source_file_storage == "uploaded_copy"
    assert "七天内可以申请退货" in document.content_text


def test_import_knowledge_file_reads_docx_and_xlsx(tmp_path):
    db = make_session()
    docx_path = tmp_path / "升级手册.docx"
    doc = Document()
    doc.add_paragraph("升级手册")
    doc.add_paragraph("升级前需要备份配置。")
    doc.save(docx_path)

    xlsx_path = tmp_path / "售后FAQ.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["问题", "答案"])
    sheet.append(["发票抬头写错", "未开票可修改，已开票需作废重开。"])
    workbook.save(xlsx_path)

    docx_result = import_knowledge_file(db, filename=docx_path.name, content=docx_path.read_bytes(), user_id="agent-1")
    xlsx_result = import_knowledge_file(db, filename=xlsx_path.name, content=xlsx_path.read_bytes(), user_id="agent-1")

    assert docx_result["imported_count"] == 1
    assert xlsx_result["imported_count"] == 1
    documents = db.query(KnowledgeDocument).order_by(KnowledgeDocument.title.asc()).all()
    assert {document.source_file_name for document in documents} == {"升级手册.docx", "售后FAQ.xlsx"}
    assert any("升级前需要备份配置" in document.content_text for document in documents)
    assert any("发票抬头写错" in document.content_text for document in documents)
