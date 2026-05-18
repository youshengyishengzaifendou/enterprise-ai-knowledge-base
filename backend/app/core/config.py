from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "sqlite:///./enterprise_ai_assistant.db"
    agent_tool_api_key: str | None = None
    allow_unbound_agent_actor_fallback: bool | None = None
    legacy_global_channel_actors: str = (
        "feishu:ou_8d05034bd270234aff8cdefa87f2a5ba,"
        "openclaw-weixin:o9cq802PIeLu2hwzpSRvdxMcisHI@im.wechat,"
        "openclaw-weixin:o9cq801FsEsSNQ-z6MR_xQz6yb1Q@im.wechat,"
        "openclaw-weixin:o9cq80_Nzy2o1HWNJvJcOVo9BdJI@im.wechat,"
        "openclaw-weixin:1d1dcf8714e5-im-bot,"
        "openclaw-weixin:3f81836398cd-im-bot,"
        "openclaw-weixin:a0804972d9df-im-bot"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
