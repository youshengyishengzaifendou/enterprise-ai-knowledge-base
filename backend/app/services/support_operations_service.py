from collections import Counter
import csv
from io import StringIO
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, KnowledgeChunk, KnowledgeDocument, SupportUnansweredQuestion
from app.services.knowledge_service import ingest_document


def record_unanswered_question(
    db: Session,
    *,
    question: str,
    user_id: str | None = None,
    customer_id: str | None = None,
    project_id: str | None = None,
    source: str = "kb_answer",
) -> SupportUnansweredQuestion | None:
    normalized_question = question.strip()
    if not normalized_question:
        return None

    existing = db.scalar(
        select(SupportUnansweredQuestion).where(
            SupportUnansweredQuestion.question == normalized_question,
            SupportUnansweredQuestion.status == "pending",
        )
    )
    if existing:
        return existing

    row = SupportUnansweredQuestion(
        question=normalized_question,
        user_id=user_id,
        customer_id=customer_id,
        project_id=project_id,
        source=source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_unanswered_questions(db: Session, *, limit: int = 25, status: str | None = None) -> list[dict[str, Any]]:
    query = select(SupportUnansweredQuestion)
    if status:
        query = query.where(SupportUnansweredQuestion.status == status)
    rows = db.scalars(query.order_by(SupportUnansweredQuestion.created_at.desc()).limit(limit)).all()
    return [_serialize_unanswered(row) for row in rows]


def update_unanswered_question_status(db: Session, unanswered_id: str, *, status: str) -> dict[str, Any]:
    if status not in {"pending", "resolved", "ignored"}:
        raise ValueError("status must be pending, resolved, or ignored")
    row = db.get(SupportUnansweredQuestion, unanswered_id)
    if row is None:
        raise ValueError("unanswered question not found")
    row.status = status
    db.commit()
    db.refresh(row)
    return _serialize_unanswered(row)


def get_support_operations_dashboard(db: Session, *, limit: int = 10) -> dict[str, Any]:
    total_queries = _count_kb_answer_logs(db)
    unanswered_count = int(db.scalar(select(func.count()).select_from(SupportUnansweredQuestion)) or 0)
    missed_queries = max(_count_missed_answer_logs(db), unanswered_count)
    hit_queries = max(total_queries - missed_queries, 0)
    document_count = int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0)
    chunk_count = int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0)

    return {
        "ok": True,
        "metrics": {
            "knowledge_documents": document_count,
            "answer_fragments": chunk_count,
            "total_queries": total_queries,
            "hit_queries": hit_queries,
            "missed_queries": missed_queries,
            "unanswered_questions": unanswered_count,
            "hit_rate": round(hit_queries / total_queries, 4) if total_queries else 0,
        },
        "popular_questions": _popular_questions(db, limit),
        "recent_unanswered": list_unanswered_questions(db, limit=limit),
        "recent_documents": _recent_documents(db, limit),
    }


def import_faq_text(
    db: Session,
    *,
    text: str,
    user_id: str,
    source_type: str = "faq_import",
    customer_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    rows = _parse_faq_rows(text)
    imported = []
    for question, answer in rows:
        document = ingest_document(
            db,
            payload={
                "title": question,
                "summary": answer[:120],
                "content_text": f"问题：{question}\n答案：{answer}",
                "source_type": source_type,
                "customer_id": customer_id,
                "project_id": project_id,
            },
            user_id=user_id,
        )
        imported.append({"id": document.id, "title": document.title})

    return {
        "ok": True,
        "imported_count": len(imported),
        "documents": imported,
    }


def _parse_faq_rows(text: str) -> list[tuple[str, str]]:
    stripped = text.strip()
    if not stripped:
        return []

    if "," in stripped.splitlines()[0]:
        reader = csv.DictReader(StringIO(stripped))
        if reader.fieldnames and {"问题", "答案"}.issubset(set(reader.fieldnames)):
            return [
                (str(row.get("问题") or "").strip(), str(row.get("答案") or "").strip())
                for row in reader
                if str(row.get("问题") or "").strip() and str(row.get("答案") or "").strip()
            ]

    if stripped.startswith("#"):
        lines = stripped.splitlines()
        title = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
        if title and body:
            return [(title, body)]

    rows: list[tuple[str, str]] = []
    for block in stripped.split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        question = ""
        answer = ""
        for line in lines:
            if line.startswith(("问题：", "问题:", "Q:", "Q：")):
                question = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            elif line.startswith(("答案：", "答案:", "A:", "A：")):
                answer = line.split(":", 1)[-1].split("：", 1)[-1].strip()
        if question and answer:
            rows.append((question, answer))
    if rows:
        return rows

    plain_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(plain_lines) >= 2:
        return [(plain_lines[0], "\n".join(plain_lines[1:]))]

    return []


def _count_kb_answer_logs(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.tool_name == "kb_answer")) or 0)


def _count_missed_answer_logs(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.tool_name == "kb_answer", AuditLog.response_summary.contains("没有找到"))
        )
        or 0
    )


def _popular_questions(db: Session, limit: int) -> list[dict[str, Any]]:
    logs = db.scalars(select(AuditLog).where(AuditLog.tool_name == "kb_answer")).all()
    counts: Counter[str] = Counter()
    for log in logs:
        question = _extract_query(log.request_payload)
        if question:
            counts[question] += 1
    return [{"question": question, "count": count} for question, count in counts.most_common(limit)]


def _extract_query(payload: dict[str, Any]) -> str:
    input_payload = payload.get("input") if isinstance(payload.get("input"), dict) else payload
    value = input_payload.get("query") if isinstance(input_payload, dict) else None
    return str(value or "").strip()


def _recent_documents(db: Session, limit: int) -> list[dict[str, Any]]:
    rows = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "summary": row.summary,
            "source_type": row.source_type,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


def _serialize_unanswered(row: SupportUnansweredQuestion) -> dict[str, Any]:
    return {
        "id": row.id,
        "question": row.question,
        "customer_id": row.customer_id,
        "project_id": row.project_id,
        "user_id": row.user_id,
        "status": row.status,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
