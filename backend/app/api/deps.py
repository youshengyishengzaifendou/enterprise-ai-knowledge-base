from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas.agent_tools import Actor
from app.services.identity_service import resolve_actor


def get_current_actor(
    db: Session = Depends(get_db),
    x_actor_channel: str = Header(default="web"),
    x_actor_external_user_id: str = Header(default="demo-user"),
    x_actor_internal_user_id: str | None = Header(default=None),
) -> User:
    actor = Actor(
        channel=x_actor_channel,
        external_user_id=x_actor_external_user_id,
        internal_user_id=x_actor_internal_user_id,
    )
    user = resolve_actor(db, actor)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown actor.")
    return user
