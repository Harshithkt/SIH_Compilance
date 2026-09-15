import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from app.auth import require_role
from app.config import settings
from app.models import User
from app.seed import seed

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/seed")
def seed_demo_data(
    x_seed_secret: str | None = Header(default=None),
    _: User = Depends(require_role("admin")),
):
    """Rebuild the demo dataset. The secret decides whether this endpoint exists in a
    deployment at all; the admin role decides who may then call it."""
    if not settings.seed_secret:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_seed_secret or not secrets.compare_digest(x_seed_secret, settings.seed_secret):
        raise HTTPException(status_code=403, detail="Invalid seed secret")

    seed()
    return {"status": "ok", "message": "Demo data seeded"}