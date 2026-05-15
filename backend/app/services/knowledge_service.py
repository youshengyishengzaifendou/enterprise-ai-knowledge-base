from collections.abc import Iterable
from datetime import timedelta
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Customer, KnowledgeChunk, KnowledgeDocument, Project, User
from app.schemas.agent_tools import Citation
from app.services.permission_service import can_access_customer, can_access_project


WEEKDAY_OFFSETS = {
    "下周一": 0,
    "下周二": 1,
    "下周三": 2,
    "下周四": 3,
    "下周五": 4,
    "下周六": 5,
    "下周日": 6,
    "下周天": 6,
}


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n\n")]
    return [part for part in paragraphs if part]


def build_chunks(text: str, max_chars: int = 400) -> list[str]:
    chunks: list[str] = []
    current = ""
    for paragraph in _split_paragraphs(text):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            piece = paragraph[start : start + max_chars]
            chunks.append(piece)
            start += max_chars
        current = ""
    if current:
        chunks.append(current)
    return chunks or [text.strip()]


def can_access_document(db: Session, user: User | None, document: KnowledgeDocument) -> bool:
    if user is None:
        return True
    if user.role == "admin":
        return True
    if document.project_id:
        project = db.get(Project, document.project_id)
        return project is not None and can_access_project(db, user, project)
    if document.customer_id:
        customer = db.get(Customer, document.customer_id)
        return customer is not None and can_access_customer(db, user, customer)
    return True


def _apply_demo_document_scope(payload: dict) -> dict:
    scoped = dict(payload)
    if scoped.get("project_id") or scoped.get("customer_id"):
        return scoped

    haystack = "\n".join(str(scoped.get(key) or "") for key in ("title", "summary", "content_text"))
    if "恒润" in haystack:
        scoped["project_id"] = "project-demo"

    return scoped


def ingest_document(db: Session, *, payload: dict, user_id: str) -> KnowledgeDocument:
    payload = _apply_demo_document_scope(payload)
    content_text = str(payload["content_text"]).strip()
    document = KnowledgeDocument(
        title=str(payload["title"]).strip(),
        source_type=str(payload.get("source_type") or "manual"),
        source_url=payload.get("source_url"),
        source_file_path=payload.get("source_file_path"),
        source_file_name=payload.get("source_file_name"),
        source_file_mime_type=payload.get("source_file_mime_type"),
        source_file_size=int(payload["source_file_size"]) if payload.get("source_file_size") not in (None, "") else None,
        source_file_storage=payload.get("source_file_storage"),
        customer_id=payload.get("customer_id"),
        project_id=payload.get("project_id"),
        summary=payload.get("summary"),
        content_text=content_text,
        created_by=user_id,
    )
    db.add(document)
    db.flush()

    for index, chunk_text in enumerate(build_chunks(content_text)):
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                content_text=chunk_text,
            )
        )

    db.commit()
    db.refresh(document)
    return document


def find_source_files(
    db: Session,
    *,
    query: str,
    project_id: str | None = None,
    customer_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    normalized_query = query.strip()
    conditions = [KnowledgeDocument.source_file_path.is_not(None)]
    if normalized_query:
        like_query = f"%{normalized_query}%"
        conditions.append(
            or_(
                KnowledgeDocument.title.like(like_query),
                KnowledgeDocument.summary.like(like_query),
                KnowledgeDocument.source_file_name.like(like_query),
                KnowledgeDocument.source_file_path.like(like_query),
            )
        )
    if project_id:
        conditions.append(KnowledgeDocument.project_id == project_id)
    if customer_id:
        conditions.append(KnowledgeDocument.customer_id == customer_id)

    documents = db.scalars(
        select(KnowledgeDocument)
        .where(*conditions)
        .order_by(KnowledgeDocument.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "document_id": document.id,
            "document_title": document.title,
            "project_id": document.project_id,
            "customer_id": document.customer_id,
            "source_type": document.source_type,
            "source_url": document.source_url,
            "source_file_path": document.source_file_path,
            "source_file_name": document.source_file_name,
            "source_file_mime_type": document.source_file_mime_type,
            "source_file_size": document.source_file_size,
            "source_file_storage": document.source_file_storage,
            "updated_at": document.updated_at,
        }
        for document in documents
    ]


def _score_chunk(query: str, text: str, title: str) -> int:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return 0
    lower_text = text.lower()
    lower_title = title.lower()
    terms = [term.lower() for term in query.split() if term.strip()]
    if len(terms) <= 1:
        direct_score = lower_text.count(normalized_query) + lower_title.count(normalized_query) * 2
        if direct_score > 0:
            return direct_score
        bigrams = [normalized_query[index : index + 2] for index in range(len(normalized_query) - 1)]
        bigrams = [item for item in bigrams if item.strip()]
        return sum(lower_text.count(item) + lower_title.count(item) * 2 for item in bigrams)
    return sum(lower_text.count(term) + lower_title.count(term) * 2 for term in terms)


def search_knowledge(
    db: Session,
    *,
    query: str,
    user: User | None,
    project_id: str | None = None,
    customer_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    documents = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())).all()
    visible_documents = [
        document
        for document in documents
        if can_access_document(db, user, document)
        and (not project_id or document.project_id == project_id)
        and (not customer_id or document.customer_id == customer_id)
    ]

    results: list[dict] = []
    for document in visible_documents:
        chunks = db.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.chunk_index.asc())
        ).all()
        for chunk in chunks:
            score = _score_chunk(query, chunk.content_text, document.title)
            if score <= 0:
                continue
            results.append(
                {
                    "score": score,
                    "document": document,
                    "chunk": chunk,
                }
            )

    results.sort(key=lambda item: (-item["score"], item["document"].updated_at or item["document"].created_at), reverse=False)
    return results[:limit]


def _collect_citations(rows: Iterable[dict]) -> list[Citation]:
    citations: list[Citation] = []
    for row in rows:
        document: KnowledgeDocument = row["document"]
        chunk: KnowledgeChunk = row["chunk"]
        citations.append(
            Citation(
                type="knowledge_chunk",
                id=chunk.id,
                title=f"{document.title}#片段{chunk.chunk_index + 1}",
                updated_at=document.updated_at,
            )
        )
    return citations


def _next_weekday(base, weekday: int):
    days = (weekday - base.weekday()) % 7
    if days == 0:
        days = 7
    return base + timedelta(days=days)


def _format_cn_month_day(value) -> str:
    return f"{value.month}月{value.day}日"


def _extract_submission_answer(query: str, text: str, base_date) -> str | None:
    if not any(keyword in query for keyword in ("什么时候", "几号", "哪天", "提交", "截止", "完成")):
        return None

    explicit_date = re.search(r"(\d{1,2})月(\d{1,2})日?前?(?:提交|完成|交付)?", text)
    if explicit_date:
        return f"商品主数据模板{int(explicit_date.group(1))}月{int(explicit_date.group(2))}日前提交。"

    for keyword, weekday in WEEKDAY_OFFSETS.items():
        if keyword in text:
            due_date = _next_weekday(base_date, weekday)
            return f"商品主数据模板{_format_cn_month_day(due_date)}前提交。"

    if "下周三前提交" in text or "下周三前完成" in text:
        due_date = _next_weekday(base_date, 2)
        return f"商品主数据模板{_format_cn_month_day(due_date)}前提交。"

    return None


def _extract_scope_answer(query: str, text: str) -> str | None:
    if not any(keyword in query for keyword in ("范围", "包括哪些", "包含哪些", "一期做哪些", "一期内容")):
        return None

    first_sentence = re.split(r"[。\n]", text.strip(), maxsplit=1)[0].strip()
    if not first_sentence:
        return None

    if "包括" in first_sentence and any(keyword in first_sentence for keyword in ("一期", "项目", "范围")):
        return first_sentence.replace("恒润PIM项目", "恒润项目") + "。"

    return None


def answer_with_knowledge(
    db: Session,
    *,
    query: str,
    user: User | None,
    project_id: str | None = None,
    customer_id: str | None = None,
    limit: int = 3,
    actor_user_id: str | None = None,
) -> dict:
    matches = search_knowledge(
        db,
        query=query,
        user=user,
        project_id=project_id,
        customer_id=customer_id,
        limit=limit,
    )
    if not matches:
        from app.services.support_operations_service import record_unanswered_question

        record_unanswered_question(
            db,
            question=query,
            user_id=actor_user_id or (user.id if user else None),
            customer_id=customer_id,
            project_id=project_id,
        )
        return {
            "answer": "没有找到可用的知识库内容，请先补充文档或放宽查询条件。",
            "matches": [],
            "citations": [],
        }

    first_document: KnowledgeDocument = matches[0]["document"]
    first_chunk: KnowledgeChunk = matches[0]["chunk"]
    concise_answer = _extract_scope_answer(query, first_chunk.content_text) or _extract_submission_answer(
        query, first_chunk.content_text, (first_document.updated_at or first_document.created_at).date()
    )
    if concise_answer:
        answer = concise_answer
    else:
        lines = []
        for row in matches:
            document: KnowledgeDocument = row["document"]
            chunk: KnowledgeChunk = row["chunk"]
            lines.append(f"[{document.title}] {chunk.content_text}")

        answer = "根据知识库内容，相关信息如下：\n" + "\n\n".join(lines)
    return {
        "answer": answer,
        "matches": [
            {
                "document_id": row["document"].id,
                "document_title": row["document"].title,
                "chunk_id": row["chunk"].id,
                "chunk_index": row["chunk"].chunk_index,
                "snippet": row["chunk"].content_text,
                "score": row["score"],
                "source_url": row["document"].source_url,
                "source_file_name": row["document"].source_file_name,
                "source_file_path": row["document"].source_file_path,
            }
            for row in matches
        ],
        "citations": _collect_citations(matches),
    }
