from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.dev import router as dev_router
from app.api.routes.agent_tools import router as agent_tools_router
from app.api.routes.customers import router as customers_router
from app.api.routes.database import router as database_router
from app.api.routes.projects import router as projects_router
from app.db.base import Base
from app.db.session import engine
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    if should_create_tables_on_startup():
        create_all_tables()
    yield


def should_create_tables_on_startup(app_env: str | None = None) -> bool:
    if app_env is None:
        from app.core.config import get_settings

        app_env = get_settings().app_env
    return app_env not in {"production", "prod"}


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise AI Assistant", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(127\.0\.0\.1|localhost):517[0-9]",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-actor-channel", "x-actor-external-user-id", "x-actor-internal-user-id"],
    )
    app.include_router(agent_tools_router)
    app.include_router(customers_router)
    app.include_router(database_router)
    app.include_router(projects_router)
    app.include_router(dev_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def create_all_tables() -> None:
    Base.metadata.create_all(bind=engine)
