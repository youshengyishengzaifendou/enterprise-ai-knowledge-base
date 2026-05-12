from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserChannelBinding
from app.schemas.agent_tools import Actor


def resolve_actor(db: Session, actor: Actor) -> User | None:
    if actor.internal_user_id:
        return db.get(User, actor.internal_user_id)

    user = _resolve_actor_binding(db, actor.channel, actor.external_user_id)
    if user is not None:
        return user

    if actor.channel == "openclaw" or actor.external_user_id == "unknown" or _allow_unbound_agent_actor_fallback():
        return _resolve_actor_binding(db, "openclaw", "unknown")

    return None


def _allow_unbound_agent_actor_fallback() -> bool:
    settings = get_settings()
    if settings.allow_unbound_agent_actor_fallback is not None:
        return settings.allow_unbound_agent_actor_fallback
    return settings.app_env in {"local", "test", "dev"}


def _resolve_actor_binding(db: Session, channel: str, external_user_id: str) -> User | None:
    stmt = select(User).join(
        UserChannelBinding,
        UserChannelBinding.user_id == User.id,
    ).where(
        UserChannelBinding.channel == channel,
        UserChannelBinding.external_user_id == external_user_id,
        User.status == "active",
    )
    return db.scalar(stmt)
