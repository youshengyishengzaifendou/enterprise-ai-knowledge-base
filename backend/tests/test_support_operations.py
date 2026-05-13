from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AuditLog, KnowledgeDocument, User
from app.services.knowledge_service import answer_with_knowledge
from app.services.support_operations_service import (
    get_support_operations_dashboard,
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
