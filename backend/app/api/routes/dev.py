from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.seed_service import seed_demo_data

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/seed-demo")
def seed_demo(db: Session = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    if settings.app_env not in {"local", "test", "dev"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo seeding is disabled outside local/dev/test environments.",
        )
    return {"ok": True, "data": seed_demo_data(db)}
