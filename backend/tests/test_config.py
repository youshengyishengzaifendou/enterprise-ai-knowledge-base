from app.core.config import Settings
from app.main import create_app


def test_settings_ignores_openclaw_client_side_environment_variables(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=local",
                "DATABASE_URL=sqlite:///./enterprise_ai_assistant.db",
                "AGENT_TOOL_API_KEY=local-key",
                "ENTERPRISE_AI_BACKEND_URL=http://127.0.0.1:8000",
                "ENTERPRISE_AI_AGENT_TOOL_API_KEY=local-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_env == "local"
    assert settings.database_url == "sqlite:///./enterprise_ai_assistant.db"
    assert settings.agent_tool_api_key == "local-key"


def test_cors_allows_container_frontend_port():
    app = create_app()
    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")

    assert "http://localhost:8080" in cors.kwargs["allow_origins"]
    assert "http://127.0.0.1:8080" in cors.kwargs["allow_origins"]
