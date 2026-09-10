from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services import nebius, ocr

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health")
def health():
    provider = ocr.get_provider(settings.ocr_provider)
    return {
        "status": "ok",
        "active_rule_version": settings.active_rule_version,
        "text_recognition_provider": provider.name,
        "nebius_configured": nebius.is_configured(),
        "nebius_base_url": settings.nebius_base_url,
        "vision_model": settings.nebius_vision_model,
        "text_model": settings.nebius_text_model,
    }


@router.get("/models")
def models():
    """Live Nebius catalogue for this account — confirms which vision/text model IDs are
    actually available before pinning them in configuration.
    """
    try:
        return {"models": nebius.list_models()}
    except nebius.NebiusError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
