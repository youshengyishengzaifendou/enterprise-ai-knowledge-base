from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_agent_tool_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = get_settings().agent_tool_api_key
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid agent tool API key.",
        )

