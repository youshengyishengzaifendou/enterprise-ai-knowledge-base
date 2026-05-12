from sqlalchemy.orm import Session

from app.models import AuditLog
from app.schemas.agent_tools import AgentToolRequest, AgentToolResponse


def write_audit_log(
    db: Session,
    *,
    request: AgentToolRequest,
    response: AgentToolResponse,
    user_id: str | None,
    tool_name: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> None:
    log = AuditLog(
        user_id=user_id,
        channel=request.actor.channel,
        action=action,
        tool_name=tool_name,
        response_summary=response.message,
        target_type=target_type,
        target_id=target_id,
    )
    log.request_payload = request.model_dump(mode="json")
    db.add(log)
    db.commit()

