from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import ConfirmationAction


def create_confirmation(db: Session, *, user_id: str, action: str, summary: str, payload: dict[str, Any]) -> ConfirmationAction:
    confirmation = ConfirmationAction(
        actor_user_id=user_id,
        action=action,
        summary=summary,
        expires_at=datetime.now() + timedelta(minutes=10),
    )
    confirmation.payload = payload
    db.add(confirmation)
    db.commit()
    db.refresh(confirmation)
    return confirmation


def get_pending_confirmation(db: Session, confirmation_id: str, user_id: str) -> ConfirmationAction | None:
    confirmation = db.get(ConfirmationAction, confirmation_id)
    if confirmation is None or confirmation.actor_user_id != user_id or confirmation.status != "pending":
        return None
    return confirmation


def mark_completed(db: Session, confirmation: ConfirmationAction) -> None:
    confirmation.status = "completed"
    confirmation.completed_at = datetime.now()
    db.add(confirmation)
    db.commit()

