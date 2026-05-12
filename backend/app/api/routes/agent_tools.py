from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_agent_tool_api_key
from app.db.session import get_db
from app.models import Customer, KnowledgeDocument, Project, User
from app.schemas.agent_tools import AgentToolRequest, AgentToolResponse, ConfirmationPayload
from app.services.audit_service import write_audit_log
from app.services.confirmation_service import create_confirmation, get_pending_confirmation, mark_completed
from app.services.extraction_service import extract_project_update
from app.services.identity_service import resolve_actor
from app.services.knowledge_service import answer_with_knowledge, can_access_document, ingest_document, search_knowledge
from app.services.project_service import (
    create_project_event,
    create_project_task,
    get_project_brief,
    search_customers,
    search_projects,
)
from app.services.permission_service import can_access_project

router = APIRouter(prefix="/api/agent-tools", tags=["agent-tools"], dependencies=[Depends(require_agent_tool_api_key)])


def _unauthorized() -> AgentToolResponse:
    return AgentToolResponse(ok=False, error_code="UNAUTHORIZED", message="无法识别当前用户。")


def _permission_denied() -> AgentToolResponse:
    return AgentToolResponse(ok=False, error_code="PERMISSION_DENIED", message="你没有权限访问该项目。")


def _with_audit(
    db: Session,
    request: AgentToolRequest,
    response: AgentToolResponse,
    user_id: str | None,
    tool_name: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> AgentToolResponse:
    write_audit_log(
        db,
        request=request,
        response=response,
        user_id=user_id,
        tool_name=tool_name,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    return response


def _authorized_project(db: Session, user: User, project_id: object) -> Project | None:
    if project_id is None:
        return None
    project = db.get(Project, str(project_id))
    if project is None or not can_access_project(db, user, project):
        return None
    return project


def _authorized_customer(db: Session, user: User, customer_id: object) -> Customer | None:
    if customer_id is None:
        return None
    customer = db.get(Customer, str(customer_id))
    if customer is None:
        return None
    from app.services.permission_service import can_access_customer

    if not can_access_customer(db, user, customer):
        return None
    return customer


@router.post("/customer_search", response_model=AgentToolResponse)
def customer_search(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    query = str(request.input.get("query", "")).strip()
    customers = search_customers(db, query, user=None)
    response = AgentToolResponse(
        ok=True,
        data={"customers": [{"id": item.id, "name": item.name, "status": item.status, "owner_user_id": item.owner_user_id} for item in customers]},
        message=f"找到 {len(customers)} 个客户。",
    )
    return _with_audit(db, request, response, user.id if user else None, "customer_search", "query")


@router.post("/project_search", response_model=AgentToolResponse)
def project_search(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    query = str(request.input.get("query", "")).strip()
    projects = search_projects(db, query, request.input.get("customer_id"), user=None)
    response = AgentToolResponse(
        ok=True,
        data={"projects": [{"id": item.id, "customer_id": item.customer_id, "name": item.name, "stage": item.stage, "status": item.status} for item in projects]},
        message=f"找到 {len(projects)} 个项目。",
    )
    return _with_audit(db, request, response, user.id if user else None, "project_search", "query")


@router.post("/project_extract_update", response_model=AgentToolResponse)
def project_extract_update(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    if user is None:
        return _with_audit(db, request, _unauthorized(), None, "project_extract_update", "denied")
    text = str(request.input.get("text", ""))
    message_time_raw = request.input.get("message_time")
    message_time = datetime.fromisoformat(message_time_raw) if message_time_raw else datetime.now()
    draft = extract_project_update(text, message_time)
    response = AgentToolResponse(
        ok=True,
        data={"draft": draft.model_dump(mode="json")},
        message="已生成项目进展草稿，写入前需要用户确认。",
    )
    return _with_audit(db, request, response, user.id, "project_extract_update", "extract")


@router.post("/project_add_update", response_model=AgentToolResponse)
def project_add_update(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    if user is None:
        return _with_audit(db, request, _unauthorized(), None, "project_add_update", "denied")

    project = _authorized_project(db, user, request.input.get("project_id"))
    if project is None:
        return _with_audit(db, request, _permission_denied(), user.id, "project_add_update", "permission_denied", "project", request.input.get("project_id"))

    if not request.input.get("confirmed", False):
        summary = f"写入项目进展：{request.input.get('title', '项目进展')}"
        confirmation = create_confirmation(db, user_id=user.id, action="project_add_update", summary=summary, payload=request.input)
        response = AgentToolResponse(
            ok=True,
            data={"pending_payload": request.input},
            need_confirmation=True,
            confirmation=ConfirmationPayload(
                confirmation_id=confirmation.id,
                title="确认写入项目进展",
                summary=summary,
                expires_at=confirmation.expires_at,
            ),
            message="写入项目进展前需要用户确认。",
        )
        return _with_audit(db, request, response, user.id, "project_add_update", "confirm_required", "confirmation", confirmation.id)

    event = create_project_event(db, payload=request.input, user_id=user.id, source_url=request.trace.source_url)
    response = AgentToolResponse(
        ok=True,
        data={"event": {"id": event.id, "project_id": event.project_id, "title": event.title}},
        citations=[{"type": "project_event", "id": event.id, "title": event.title, "updated_at": event.event_time}],
        message="已记录项目进展。",
    )
    return _with_audit(db, request, response, user.id, "project_add_update", "write", "project_event", event.id)


@router.post("/task_create", response_model=AgentToolResponse)
def task_create(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    if user is None:
        return _with_audit(db, request, _unauthorized(), None, "task_create", "denied")

    project = _authorized_project(db, user, request.input.get("project_id"))
    if project is None:
        return _with_audit(db, request, _permission_denied(), user.id, "task_create", "permission_denied", "project", request.input.get("project_id"))

    if not request.input.get("confirmed", False):
        summary = f"创建任务：{request.input.get('title', '项目任务')}"
        confirmation = create_confirmation(db, user_id=user.id, action="task_create", summary=summary, payload=request.input)
        response = AgentToolResponse(
            ok=True,
            data={"pending_payload": request.input},
            need_confirmation=True,
            confirmation=ConfirmationPayload(
                confirmation_id=confirmation.id,
                title="确认创建项目任务",
                summary=summary,
                expires_at=confirmation.expires_at,
            ),
            message="创建任务前需要用户确认。",
        )
        return _with_audit(db, request, response, user.id, "task_create", "confirm_required", "confirmation", confirmation.id)

    task = create_project_task(db, payload=request.input, user_id=user.id)
    response = AgentToolResponse(
        ok=True,
        data={"task": {"id": task.id, "project_id": task.project_id, "title": task.title, "due_date": task.due_date}},
        message="已创建项目任务。",
    )
    return _with_audit(db, request, response, user.id, "task_create", "write", "project_task", task.id)


@router.post("/project_get_brief", response_model=AgentToolResponse)
def project_get_brief(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    project = db.get(Project, str(request.input["project_id"]))
    if project is None:
        response = _permission_denied()
        return _with_audit(db, request, response, user.id if user else None, "project_get_brief", "permission_denied", "project", request.input["project_id"])
    brief = get_project_brief(db, str(request.input["project_id"]))
    citations = brief.pop("citations")
    response = AgentToolResponse(
        ok=True,
        data=brief,
        citations=citations,
        message=f"项目 {brief['project']['name']} 当前阶段为 {brief['project']['stage']}。",
    )
    return _with_audit(db, request, response, user.id if user else None, "project_get_brief", "query", "project", brief["project"]["id"])


@router.post("/confirm_action", response_model=AgentToolResponse)
def confirm_action(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    if user is None:
        return _with_audit(db, request, _unauthorized(), None, "confirm_action", "denied")
    confirmation = get_pending_confirmation(db, str(request.input["confirmation_id"]), user.id)
    if confirmation is None:
        response = AgentToolResponse(ok=False, error_code="CONFIRMATION_NOT_FOUND", message="确认请求不存在或已处理。")
        return _with_audit(db, request, response, user.id, "confirm_action", "not_found")

    payload = confirmation.payload
    payload["confirmed"] = True
    project = _authorized_project(db, user, payload.get("project_id"))
    if project is None:
        response = _permission_denied()
        return _with_audit(db, request, response, user.id, "confirm_action", "permission_denied", "project", payload.get("project_id"))
    if confirmation.action == "project_add_update":
        event = create_project_event(db, payload=payload, user_id=user.id, source_url=request.trace.source_url)
        mark_completed(db, confirmation)
        response = AgentToolResponse(
            ok=True,
            data={"event": {"id": event.id, "project_id": event.project_id, "title": event.title}},
            citations=[{"type": "project_event", "id": event.id, "title": event.title, "updated_at": event.event_time}],
            message="已确认并写入项目进展。",
        )
        return _with_audit(db, request, response, user.id, "confirm_action", "write", "project_event", event.id)

    if confirmation.action == "task_create":
        task = create_project_task(db, payload=payload, user_id=user.id)
        mark_completed(db, confirmation)
        response = AgentToolResponse(
            ok=True,
            data={"task": {"id": task.id, "project_id": task.project_id, "title": task.title, "due_date": task.due_date}},
            message="已确认并创建项目任务。",
        )
        return _with_audit(db, request, response, user.id, "confirm_action", "write", "project_task", task.id)

    if confirmation.action == "kb_ingest_document":
        document = ingest_document(db, payload=payload, user_id=user.id)
        mark_completed(db, confirmation)
        response = AgentToolResponse(
            ok=True,
            data={"document": {"id": document.id, "title": document.title, "project_id": document.project_id, "customer_id": document.customer_id}},
            citations=[{"type": "knowledge_document", "id": document.id, "title": document.title, "updated_at": document.updated_at}],
            message="已确认并写入知识库文档。",
        )
        return _with_audit(db, request, response, user.id, "confirm_action", "write", "knowledge_document", document.id)

    response = AgentToolResponse(ok=False, error_code="UNSUPPORTED_ACTION", message="不支持的确认动作。")
    return _with_audit(db, request, response, user.id, "confirm_action", "unsupported")


@router.post("/kb_ingest_document", response_model=AgentToolResponse)
def kb_ingest_document(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)
    if user is None:
        return _with_audit(db, request, _unauthorized(), None, "kb_ingest_document", "denied")

    project_id = request.input.get("project_id")
    customer_id = request.input.get("customer_id")
    if project_id and _authorized_project(db, user, project_id) is None:
        return _with_audit(db, request, _permission_denied(), user.id, "kb_ingest_document", "permission_denied", "project", project_id)
    if not project_id and customer_id and _authorized_customer(db, user, customer_id) is None:
        return _with_audit(db, request, _permission_denied(), user.id, "kb_ingest_document", "permission_denied", "customer", customer_id)

    if not request.input.get("confirmed", False):
        summary = f"写入知识库文档：{request.input.get('title', '未命名文档')}"
        confirmation = create_confirmation(db, user_id=user.id, action="kb_ingest_document", summary=summary, payload=request.input)
        response = AgentToolResponse(
            ok=True,
            data={"pending_payload": request.input},
            need_confirmation=True,
            confirmation=ConfirmationPayload(
                confirmation_id=confirmation.id,
                title="确认写入知识库文档",
                summary=summary,
                expires_at=confirmation.expires_at,
            ),
            message="写入知识库文档前需要用户确认。",
        )
        return _with_audit(db, request, response, user.id, "kb_ingest_document", "confirm_required", "confirmation", confirmation.id)

    document = ingest_document(db, payload=request.input, user_id=user.id)
    response = AgentToolResponse(
        ok=True,
        data={"document": {"id": document.id, "title": document.title, "project_id": document.project_id, "customer_id": document.customer_id}},
        citations=[{"type": "knowledge_document", "id": document.id, "title": document.title, "updated_at": document.updated_at}],
        message="已写入知识库文档。",
    )
    return _with_audit(db, request, response, user.id, "kb_ingest_document", "write", "knowledge_document", document.id)


@router.post("/kb_search", response_model=AgentToolResponse)
def kb_search(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)

    matches = search_knowledge(
        db,
        query=str(request.input.get("query", "")).strip(),
        user=None,
        project_id=request.input.get("project_id"),
        customer_id=request.input.get("customer_id"),
        limit=int(request.input.get("limit", 5)),
    )
    response = AgentToolResponse(
        ok=True,
        data={
            "matches": [
                {
                    "document_id": row["document"].id,
                    "document_title": row["document"].title,
                    "project_id": row["document"].project_id,
                    "customer_id": row["document"].customer_id,
                    "chunk_id": row["chunk"].id,
                    "chunk_index": row["chunk"].chunk_index,
                    "snippet": row["chunk"].content_text,
                    "score": row["score"],
                    "source_url": row["document"].source_url,
                }
                for row in matches
            ]
        },
        citations=[
            {"type": "knowledge_chunk", "id": row["chunk"].id, "title": f"{row['document'].title}#片段{row['chunk'].chunk_index + 1}", "updated_at": row["document"].updated_at}
            for row in matches
        ],
        message=f"找到 {len(matches)} 条知识库片段。",
    )
    return _with_audit(db, request, response, user.id if user else None, "kb_search", "query")


@router.post("/kb_answer", response_model=AgentToolResponse)
def kb_answer(request: AgentToolRequest, db: Session = Depends(get_db)) -> AgentToolResponse:
    user = resolve_actor(db, request.actor)

    result = answer_with_knowledge(
        db,
        query=str(request.input.get("query", "")).strip(),
        user=None,
        project_id=request.input.get("project_id"),
        customer_id=request.input.get("customer_id"),
        limit=int(request.input.get("limit", 3)),
    )
    response = AgentToolResponse(
        ok=True,
        data={"answer": result["answer"], "matches": result["matches"]},
        citations=result["citations"],
        message="已根据知识库生成回答。",
    )
    return _with_audit(db, request, response, user.id if user else None, "kb_answer", "query")
