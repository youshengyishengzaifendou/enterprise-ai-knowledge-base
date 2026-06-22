import re

from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, User
from app.schemas.agent_tools import Citation
from app.services.knowledge_service import search_knowledge


def search_teacher_materials(
    db: Session,
    *,
    query: str,
    user: User,
    limit: int = 5,
) -> dict:
    matches = search_knowledge(db, query=query, user=user, limit=_clamp(limit, 1, 10))
    materials = [_material_from_match(row) for row in matches]
    return {
        "materials": materials,
        "citations": _citations_from_matches(matches),
    }


def generate_teacher_questions(
    db: Session,
    *,
    payload: dict,
    user: User,
) -> dict:
    topic = _clean_text(payload.get("topic")) or _clean_text(payload.get("query")) or "知识点"
    question_type = _clean_text(payload.get("question_type")) or "简答题"
    difficulty = _clean_text(payload.get("difficulty")) or "中等"
    count = _clamp(int(payload.get("count") or 3), 1, 20)
    material_id = str(payload.get("material_id") or "").strip()
    matches = _matches_for_teacher_generation(db, topic=topic, user=user, material_id=material_id, limit=max(count, 3))
    context_items = [_context_item_from_match(row) for row in matches]
    questions = [
        _build_question(
            topic=topic,
            question_type=question_type,
            difficulty=difficulty,
            index=index,
            context=context_items[index % len(context_items)] if context_items else None,
        )
        for index in range(count)
    ]
    return {
        "topic": topic,
        "question_type": question_type,
        "difficulty": difficulty,
        "questions": questions,
        "materials": context_items,
        "citations": _citations_from_matches(matches),
    }


def generate_teacher_paper(
    db: Session,
    *,
    payload: dict,
    user: User,
) -> dict:
    topic = _clean_text(payload.get("topic")) or "知识点"
    title = _clean_text(payload.get("title")) or f"{topic}测试卷"
    duration_minutes = _clamp(int(payload.get("duration_minutes") or 45), 5, 240)
    include_answers = bool(payload.get("include_answers", True))
    include_analysis = bool(payload.get("include_analysis", True))
    question_counts = _question_counts(payload.get("question_counts"))
    matches = _matches_for_teacher_generation(db, topic=topic, user=user, limit=max(sum(question_counts.values()), 5))
    context_items = [_context_item_from_match(row) for row in matches]

    sections = []
    question_index = 0
    for question_type, count in question_counts.items():
        questions = []
        for _ in range(count):
            context = context_items[question_index % len(context_items)] if context_items else None
            questions.append(
                _build_question(
                    topic=topic,
                    question_type=question_type,
                    difficulty=_clean_text(payload.get("difficulty")) or "中等",
                    index=question_index,
                    context=context,
                )
            )
            question_index += 1
        sections.append({"question_type": question_type, "count": count, "questions": questions})

    paper = {
        "title": title,
        "topic": topic,
        "paper_type": _clean_text(payload.get("paper_type")) or "quiz",
        "duration_minutes": duration_minutes,
        "include_answers": include_answers,
        "include_analysis": include_analysis,
        "sections": sections,
        "materials": context_items,
    }
    return {
        "paper": paper,
        "document_instructions": _document_generation_instructions(
            title=title,
            document_kind="teacher_paper",
            content_key="paper",
        ),
        "citations": _citations_from_matches(matches),
    }


def export_teacher_knowledge(
    db: Session,
    *,
    payload: dict,
    user: User,
) -> dict:
    topic = _clean_text(payload.get("topic")) or "知识点"
    title = _clean_text(payload.get("title")) or f"{topic}知识点整理"
    matches = _matches_for_teacher_generation(db, topic=topic, user=user, limit=5)
    context_items = [_context_item_from_match(row) for row in matches]
    edited_points = payload.get("edited_points")
    if isinstance(edited_points, list) and edited_points:
        points = [_clean_text(item) for item in edited_points if _clean_text(item)]
    else:
        points = [_point_from_context(item["snippet"]) for item in context_items]
    if not points:
        points = [f"围绕{topic}补充核心概念、常见题型和易错点。"]

    handout = {
        "title": title,
        "topic": topic,
        "stage": _clean_text(payload.get("stage")) or "all",
        "subject": _clean_text(payload.get("subject")) or "all",
        "points": points,
        "materials": context_items,
    }
    return {
        "handout": handout,
        "document_instructions": _document_generation_instructions(
            title=title,
            document_kind="teacher_handout",
            content_key="handout",
        ),
        "citations": _citations_from_matches(matches),
    }


def prepare_teacher_lesson(
    db: Session,
    *,
    payload: dict,
    user: User,
) -> dict:
    topic = _clean_text(payload.get("topic")) or "备课主题"
    title = _clean_text(payload.get("title")) or f"{topic}教案"
    lesson_hours = _clamp(int(payload.get("lesson_hours") or 1), 1, 20)
    matches = _matches_for_teacher_generation(db, topic=topic, user=user, limit=5)
    context_items = [_context_item_from_match(row) for row in matches]
    key_points = [_point_from_context(item["snippet"]) for item in context_items]
    if not key_points:
        key_points = [f"围绕{topic}明确教学重点、难点和课堂活动。"]

    lesson = {
        "title": title,
        "topic": topic,
        "stage": _clean_text(payload.get("stage")) or "all",
        "grade": _clean_text(payload.get("grade")) or "all",
        "subject": _clean_text(payload.get("subject")) or "all",
        "textbook_version": _clean_text(payload.get("textbook_version")) or "unspecified",
        "lesson_hours": lesson_hours,
        "lesson_type": _clean_text(payload.get("lesson_type")) or "新授课",
        "student_level": _clean_text(payload.get("student_level")) or "中等",
        "prep_mode": _clean_text(payload.get("prep_mode")) or "daily",
        "special_requirements": _clean_text(payload.get("special_requirements")),
        "objectives": [
            f"理解并掌握{topic}的核心概念。",
            f"能够结合资料说明{key_points[0]}。",
            "能够在典型题目或课堂任务中迁移应用相关知识。",
        ],
        "key_points": key_points,
        "teaching_flow": [
            {"stage": "导入", "activity": f"用问题或情境引出{topic}。"},
            {"stage": "新知建构", "activity": "结合知识库材料讲解核心概念、公式、结论和例题。"},
            {"stage": "课堂练习", "activity": "围绕易错点设计分层练习，及时反馈。"},
            {"stage": "总结提升", "activity": "归纳本课知识结构，布置针对性巩固任务。"},
        ],
        "materials": context_items,
    }
    return {
        "lesson": lesson,
        "document_instructions": _document_generation_instructions(
            title=title,
            document_kind="teacher_lesson",
            content_key="lesson",
        ),
        "citations": _citations_from_matches(matches),
    }


def _matches_for_teacher_generation(
    db: Session,
    *,
    topic: str,
    user: User,
    limit: int = 5,
    material_id: str = "",
) -> list[dict]:
    if material_id:
        document = db.get(KnowledgeDocument, material_id)
        if document is not None:
            chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.chunk_index.asc()).all()
            return [
                {
                    "document": document,
                    "chunk": chunk,
                    "score": 1.0,
                    "keyword_score": 1.0,
                    "vector_score": 0.0,
                    "retrieval_method": "material_id",
                }
                for chunk in chunks[:limit]
            ]
    return search_knowledge(db, query=topic, user=user, limit=_clamp(limit, 1, 20))


def _material_from_match(row: dict) -> dict:
    document: KnowledgeDocument = row["document"]
    chunk: KnowledgeChunk = row["chunk"]
    return {
        "document_id": document.id,
        "document_title": document.title,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "snippet": chunk.content_text,
        "score": row["score"],
        "source_file_name": document.source_file_name,
        "source_url": document.source_url,
        "document_version": document.current_version,
    }


def _context_item_from_match(row: dict) -> dict:
    material = _material_from_match(row)
    return {
        "document_id": material["document_id"],
        "document_title": material["document_title"],
        "chunk_id": material["chunk_id"],
        "snippet": material["snippet"],
    }


def _build_question(
    *,
    topic: str,
    question_type: str,
    difficulty: str,
    index: int,
    context: dict | None,
) -> dict:
    snippet = context["snippet"] if context else f"{topic}的核心概念和典型应用。"
    source_title = context["document_title"] if context else "未匹配资料"
    key_point = _point_from_context(snippet)
    stem = f"{index + 1}. 【{difficulty}】围绕{topic}，根据“{key_point}”设计一道{question_type}。"
    answer = _answer_for_question(question_type=question_type, topic=topic, key_point=key_point)
    return {
        "id": f"q-{index + 1}",
        "topic": topic,
        "question_type": question_type,
        "difficulty": difficulty,
        "stem": stem,
        "answer": answer,
        "analysis": f"依据资料《{source_title}》中的内容生成，重点检查学生对“{key_point}”的理解。",
        "source_document_title": source_title,
    }


def _answer_for_question(*, question_type: str, topic: str, key_point: str) -> str:
    if "选择" in question_type:
        return f"参考答案：选择能体现“{key_point}”的选项。"
    if "填空" in question_type:
        return f"参考答案：{key_point}"
    return f"参考答案要点：围绕{topic}说明{key_point}，并结合题目条件作答。"


def _point_from_context(text: str) -> str:
    normalized = " ".join(str(text).split())
    first = re.split(r"[。！？.!?；;]", normalized, maxsplit=1)[0].strip()
    if not first:
        return "核心知识点"
    return first[:80]


def _question_counts(value: object) -> dict[str, int]:
    if isinstance(value, dict) and value:
        counts = {}
        for key, count in value.items():
            label = _clean_text(key) or "简答题"
            try:
                counts[label] = _clamp(int(count), 0, 50)
            except (TypeError, ValueError):
                continue
        counts = {key: count for key, count in counts.items() if count > 0}
        if counts:
            return counts
    return {"选择题": 5, "填空题": 3, "简答题": 2}


def _document_generation_instructions(*, title: str, document_kind: str, content_key: str) -> dict:
    return {
        "owner": "openclaw",
        "format": "docx",
        "skills": ["docx", "office-word-document"],
        "document_kind": document_kind,
        "content_key": content_key,
        "suggested_file_name": f"{_safe_file_stem(title)}.docx",
        "instruction": "后端只返回结构化知识材料。请由 OpenClaw 使用 docx 或 office-word-document skill 生成 Word 文件，并将生成的文件路径或附件返回给用户。",
    }


def _safe_file_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff_.-]+", "-", value).strip("-") or "teacher-document"


def _citations_from_matches(matches: list[dict]) -> list[Citation]:
    return [
        Citation(
            type="knowledge_chunk",
            id=row["chunk"].id,
            title=f"{row['document'].title}#片段{row['chunk'].chunk_index + 1}",
            updated_at=row["document"].updated_at,
        )
        for row in matches
    ]


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
