import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserChannelBinding
from app.schemas.agent_tools import Actor

DEFAULT_LEGACY_GLOBAL_ACTORS = {
    ("feishu", "ou_8d05034bd270234aff8cdefa87f2a5ba"),
    ("openclaw-weixin", "o9cq802PIeLu2hwzpSRvdxMcisHI@im.wechat"),
    ("openclaw-weixin", "o9cq801FsEsSNQ-z6MR_xQz6yb1Q@im.wechat"),
    ("openclaw-weixin", "o9cq80_Nzy2o1HWNJvJcOVo9BdJI@im.wechat"),
    ("openclaw-weixin", "1d1dcf8714e5-im-bot"),
    ("openclaw-weixin", "3f81836398cd-im-bot"),
    ("openclaw-weixin", "a0804972d9df-im-bot"),
}
LEGACY_GLOBAL_ACTORS = DEFAULT_LEGACY_GLOBAL_ACTORS
SAFE_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,35}$")


def resolve_actor(db: Session, actor: Actor) -> User | None:
    if actor.internal_user_id:
        return db.get(User, actor.internal_user_id)

    user = _resolve_actor_binding(db, actor.channel, actor.external_user_id)
    if user is not None:
        if _is_legacy_global_actor(actor) and user.knowledge_access_policy != "all":
            user.knowledge_access_policy = "all"
            db.commit()
            db.refresh(user)
        return user

    if _actor_binding_exists(db, actor.channel, actor.external_user_id):
        return None

    if _should_auto_create_channel_user(actor):
        return _create_private_channel_user(db, actor)

    if actor.channel == "openclaw" or _is_unknown_legacy_chat_actor(actor) or _allow_unbound_agent_actor_fallback():
        return _resolve_actor_binding(db, "openclaw", "unknown")

    return None


def _should_auto_create_channel_user(actor: Actor) -> bool:
    return (
        actor.channel in {"feishu", "openclaw-weixin"}
        and bool(actor.external_user_id.strip())
        and actor.external_user_id != "unknown"
        and not actor.internal_user_id
    )


def _create_private_channel_user(db: Session, actor: Actor) -> User | None:
    is_legacy_global_actor = _is_legacy_global_actor(actor)
    external_id = actor.external_user_id.strip()
    user_id = _preferred_channel_user_id(db, external_id)
    if user_id == external_id:
        existing_user = db.get(User, user_id)
        if existing_user is not None:
            if existing_user.status != "active":
                return None
            if is_legacy_global_actor and existing_user.knowledge_access_policy != "all":
                existing_user.knowledge_access_policy = "all"
            db.add(UserChannelBinding(user_id=existing_user.id, channel=actor.channel, external_user_id=external_id))
            db.commit()
            db.refresh(existing_user)
            return existing_user

    user_kwargs = {
        "name": f"{actor.channel}:{actor.external_user_id}",
        "role": "member",
        "status": "active",
        "knowledge_access_policy": "all" if is_legacy_global_actor else "own",
    }
    if user_id is not None:
        user_kwargs["id"] = user_id
    user = User(**user_kwargs)
    db.add(user)
    db.flush()
    db.add(UserChannelBinding(user_id=user.id, channel=actor.channel, external_user_id=external_id))
    db.commit()
    db.refresh(user)
    return user


def _preferred_channel_user_id(db: Session, external_user_id: str) -> str | None:
    if SAFE_USER_ID_PATTERN.fullmatch(external_user_id):
        existing_user = db.get(User, external_user_id)
        if existing_user is None or existing_user.status == "active":
            return external_user_id
    return None


def _is_legacy_global_actor(actor: Actor) -> bool:
    return (actor.channel, actor.external_user_id) in _legacy_global_actors()


def _legacy_global_actors() -> set[tuple[str, str]]:
    settings = get_settings()
    configured = _parse_legacy_global_actors(settings.legacy_global_channel_actors)
    return configured | LEGACY_GLOBAL_ACTORS


def _parse_legacy_global_actors(value: str) -> set[tuple[str, str]]:
    actors: set[tuple[str, str]] = set()
    for item in value.split(","):
        channel, separator, external_user_id = item.strip().partition(":")
        if separator and channel and external_user_id:
            actors.add((channel, external_user_id))
    return actors


def _allow_unbound_agent_actor_fallback() -> bool:
    settings = get_settings()
    return bool(settings.allow_unbound_agent_actor_fallback)


def _is_unknown_legacy_chat_actor(actor: Actor) -> bool:
    return actor.external_user_id == "unknown" and actor.channel in {"feishu", "openclaw-weixin"}


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


def _actor_binding_exists(db: Session, channel: str, external_user_id: str) -> bool:
    binding = db.scalar(
        select(UserChannelBinding).where(
            UserChannelBinding.channel == channel,
            UserChannelBinding.external_user_id == external_user_id,
        )
    )
    return binding is not None
