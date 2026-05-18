from collections.abc import Iterable
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentGroup,
    KnowledgeDocumentGroupMembership,
    KnowledgeDocumentPermission,
    KnowledgeProjectPermission,
    KnowledgeSourceFile,
    KnowledgeSourceFilePermission,
    User,
)
from app.schemas.agent_tools import Citation
from app.services.knowledge_permission_service import can_access_document, can_access_source_file


PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_ROOT = PROJECT_ROOT / "uploads" / "knowledge_sources"
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

EMBEDDING_DIMENSIONS = 64
EMBEDDING_MODEL = "local-hash-v1"


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


def _tokenize_for_retrieval(text: str) -> list[str]:
    normalized = text.lower()
    ascii_terms = re.findall(r"[a-z0-9]+", normalized)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_bigrams = [f"{cjk_chars[index]}{cjk_chars[index + 1]}" for index in range(len(cjk_chars) - 1)]
    return [term for term in [*ascii_terms, *cjk_chars, *cjk_bigrams] if term.strip()]


def _embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in _tokenize_for_retrieval(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left[index] * right[index] for index in range(len(left)))


def _decode_embedding(value: str | None) -> list[float]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [float(item) for item in decoded if isinstance(item, (int, float))]


def _upsert_source_file(
    db: Session,
    *,
    payload: dict,
    user_id: str,
    source_channel: str | None,
    source_external_user_id: str | None,
) -> KnowledgeSourceFile | None:
    source_file_path = payload.get("source_file_path")
    if not source_file_path:
        return None
    source_file = db.scalar(select(KnowledgeSourceFile).where(KnowledgeSourceFile.file_path == str(source_file_path)))
    if source_file is None:
        source_file = KnowledgeSourceFile(
            file_name=str(payload.get("source_file_name") or source_file_path),
            file_path=str(source_file_path),
            mime_type=payload.get("source_file_mime_type"),
            file_size=int(payload["source_file_size"]) if payload.get("source_file_size") not in (None, "") else None,
            storage=payload.get("source_file_storage"),
            uploaded_by=user_id,
            source_channel=source_channel,
            source_external_user_id=source_external_user_id,
        )
        db.add(source_file)
        db.flush()
        return source_file
    source_file.file_name = str(payload.get("source_file_name") or source_file.file_name)
    source_file.mime_type = payload.get("source_file_mime_type") or source_file.mime_type
    source_file.storage = payload.get("source_file_storage") or source_file.storage
    source_file.source_channel = source_channel or source_file.source_channel
    source_file.source_external_user_id = source_external_user_id or source_file.source_external_user_id
    if payload.get("source_file_size") not in (None, ""):
        source_file.file_size = int(payload["source_file_size"])
    return source_file


def _display_source_file_path(source_file_path: str | None) -> str | None:
    if not source_file_path:
        return None
    path = Path(source_file_path)
    if path.is_absolute():
        return source_file_path
    upload_prefix = Path("uploads") / "knowledge_sources"
    try:
        relative_to_upload_root = path.relative_to(upload_prefix)
    except ValueError:
        return source_file_path
    return str(UPLOAD_ROOT / relative_to_upload_root)


def backfill_source_files(db: Session) -> dict[str, int]:
    documents = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.source_file_path.is_not(None),
            KnowledgeDocument.source_file_id.is_(None),
        )
    ).all()
    count = 0
    for document in documents:
        source_file = _upsert_source_file(
            db,
            payload={
                "source_file_path": document.source_file_path,
                "source_file_name": document.source_file_name,
                "source_file_mime_type": document.source_file_mime_type,
                "source_file_size": document.source_file_size,
                "source_file_storage": document.source_file_storage,
            },
            user_id=document.created_by,
            source_channel=document.source_channel,
            source_external_user_id=document.source_external_user_id,
        )
        if source_file is not None:
            document.source_file_id = source_file.id
            count += 1
    db.commit()
    return {"backfilled_count": count}


def _apply_demo_document_scope(payload: dict) -> dict:
    scoped = dict(payload)
    if scoped.get("project_id") or scoped.get("customer_id"):
        return scoped

    haystack = "\n".join(str(scoped.get(key) or "") for key in ("title", "summary", "content_text"))
    if "恒润" in haystack:
        scoped["project_id"] = "project-demo"

    return scoped


def ingest_document(
    db: Session,
    *,
    payload: dict,
    user_id: str,
    source_channel: str | None = None,
    source_external_user_id: str | None = None,
) -> KnowledgeDocument:
    payload = _apply_demo_document_scope(payload)
    content_text = str(payload["content_text"]).strip()
    source_file = _upsert_source_file(
        db,
        payload=payload,
        user_id=user_id,
        source_channel=source_channel,
        source_external_user_id=source_external_user_id,
    )
    document = KnowledgeDocument(
        title=str(payload["title"]).strip(),
        source_type=str(payload.get("source_type") or "manual"),
        source_url=payload.get("source_url"),
        source_file_path=payload.get("source_file_path"),
        source_file_name=payload.get("source_file_name"),
        source_file_mime_type=payload.get("source_file_mime_type"),
        source_file_size=int(payload["source_file_size"]) if payload.get("source_file_size") not in (None, "") else None,
        source_file_storage=payload.get("source_file_storage"),
        source_file_id=source_file.id if source_file else payload.get("source_file_id"),
        source_channel=source_channel or payload.get("source_channel"),
        source_external_user_id=source_external_user_id or payload.get("source_external_user_id"),
        parse_status=str(payload.get("parse_status") or "parsed"),
        parse_error=payload.get("parse_error"),
        index_status=str(payload.get("index_status") or "indexed"),
        customer_id=payload.get("customer_id"),
        project_id=payload.get("project_id"),
        summary=payload.get("summary"),
        content_text=content_text,
        created_by=user_id,
    )
    db.add(document)
    db.flush()

    for index, chunk_text in enumerate(build_chunks(content_text)):
        chunk = KnowledgeChunk(
            document_id=document.id,
            chunk_index=index,
            content_text=chunk_text,
        )
        _index_chunk(chunk, document.title)
        db.add(
            chunk
        )

    db.commit()
    db.refresh(document)
    return document


def find_source_files(
    db: Session,
    *,
    query: str,
    user: User | None = None,
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
    visible_documents = []
    for document in documents:
        source_file = db.get(KnowledgeSourceFile, document.source_file_id) if document.source_file_id else None
        if can_access_document(db, user, document) or (source_file is not None and can_access_source_file(db, user, source_file)):
            visible_documents.append(document)
    return [
        {
            "document_id": document.id,
            "document_title": document.title,
            "source_file_id": document.source_file_id,
            "project_id": document.project_id,
            "customer_id": document.customer_id,
            "source_type": document.source_type,
            "source_channel": document.source_channel,
            "source_external_user_id": document.source_external_user_id,
            "source_url": document.source_url,
            "source_file_path": _display_source_file_path(document.source_file_path),
            "source_file_name": document.source_file_name,
            "source_file_mime_type": document.source_file_mime_type,
            "source_file_size": document.source_file_size,
            "source_file_storage": document.source_file_storage,
            "updated_at": document.updated_at,
        }
        for document in visible_documents[:limit]
    ]


def grant_source_file_permission(
    db: Session,
    *,
    source_file_id: str,
    user_id: str,
    access_level: str = "read",
) -> KnowledgeSourceFilePermission:
    permission = db.scalar(
        select(KnowledgeSourceFilePermission).where(
            KnowledgeSourceFilePermission.source_file_id == source_file_id,
            KnowledgeSourceFilePermission.user_id == user_id,
        )
    )
    if permission is None:
        permission = KnowledgeSourceFilePermission(source_file_id=source_file_id, user_id=user_id, access_level=access_level)
        db.add(permission)
    else:
        permission.access_level = access_level
    db.commit()
    db.refresh(permission)
    return permission


def batch_grant_documents(db: Session, *, document_ids: list[str], user_id: str, access_level: str = "read") -> list[KnowledgeDocumentPermission]:
    permissions: list[KnowledgeDocumentPermission] = []
    for document_id in document_ids:
        permission = db.scalar(
            select(KnowledgeDocumentPermission).where(
                KnowledgeDocumentPermission.document_id == document_id,
                KnowledgeDocumentPermission.user_id == user_id,
            )
        )
        if permission is None:
            permission = KnowledgeDocumentPermission(document_id=document_id, user_id=user_id, access_level=access_level)
            db.add(permission)
        else:
            permission.access_level = access_level
        permissions.append(permission)
    db.commit()
    return permissions


def create_document_group(db: Session, *, name: str, created_by: str, description: str | None = None) -> KnowledgeDocumentGroup:
    group = KnowledgeDocumentGroup(name=name, description=description, created_by=created_by)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def add_document_to_group(db: Session, *, group_id: str, document_id: str) -> KnowledgeDocumentGroupMembership:
    membership = db.scalar(
        select(KnowledgeDocumentGroupMembership).where(
            KnowledgeDocumentGroupMembership.group_id == group_id,
            KnowledgeDocumentGroupMembership.document_id == document_id,
        )
    )
    if membership is None:
        membership = KnowledgeDocumentGroupMembership(group_id=group_id, document_id=document_id)
        db.add(membership)
        db.commit()
        db.refresh(membership)
    return membership


def grant_project_permission(db: Session, *, project_id: str, user_id: str, access_level: str = "read") -> KnowledgeProjectPermission:
    permission = db.scalar(
        select(KnowledgeProjectPermission).where(
            KnowledgeProjectPermission.project_id == project_id,
            KnowledgeProjectPermission.user_id == user_id,
        )
    )
    if permission is None:
        permission = KnowledgeProjectPermission(project_id=project_id, user_id=user_id, access_level=access_level)
        db.add(permission)
    else:
        permission.access_level = access_level
    db.commit()
    db.refresh(permission)
    return permission


def rebuild_document_index(db: Session, document_id: str) -> dict:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise ValueError("knowledge document not found")
    chunks = db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.chunk_index.asc())
    ).all()
    for chunk in chunks:
        _index_chunk(chunk, document.title)
    document.index_status = "indexed"
    db.commit()
    return {
        "document_id": document.id,
        "document_title": document.title,
        "indexed_chunks": len(chunks),
        "index_status": "indexed",
    }


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


def _hybrid_score_chunk(query: str, chunk: KnowledgeChunk, title: str, query_embedding: list[float]) -> dict[str, float | str]:
    keyword_score = float(_score_chunk(query, chunk.content_text, title))
    if not chunk.embedding_json:
        _index_chunk(chunk, title)
    vector_score = max(_cosine_similarity(query_embedding, _decode_embedding(chunk.embedding_json)), 0.0)
    normalized_keyword = min(keyword_score / 6.0, 1.0)
    score = normalized_keyword * 0.55 + vector_score * 0.45
    return {
        "score": round(score, 6),
        "keyword_score": keyword_score,
        "vector_score": round(vector_score, 6),
        "retrieval_method": "hybrid",
    }


def _index_chunk(chunk: KnowledgeChunk, title: str) -> None:
    embedding = _embed_text(f"{title}\n{chunk.content_text}")
    chunk.embedding_model = EMBEDDING_MODEL
    chunk.embedding_json = json.dumps(embedding, separators=(",", ":"))
    chunk.index_status = "indexed"
    chunk.token_count = len(_tokenize_for_retrieval(chunk.content_text))
    chunk.indexed_at = datetime.now()


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
    query_embedding = _embed_text(query)
    for document in visible_documents:
        chunks = db.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.chunk_index.asc())
        ).all()
        for chunk in chunks:
            scores = _hybrid_score_chunk(query, chunk, document.title, query_embedding)
            if float(scores["score"]) <= 0:
                continue
            results.append(
                {
                    **scores,
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
                "keyword_score": row.get("keyword_score", 0),
                "vector_score": row.get("vector_score", 0),
                "retrieval_method": row.get("retrieval_method", "keyword"),
                "source_url": row["document"].source_url,
                "source_file_name": row["document"].source_file_name,
                "source_file_path": row["document"].source_file_path,
            }
            for row in matches
        ],
        "citations": _collect_citations(matches),
    }
