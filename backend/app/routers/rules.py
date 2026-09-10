from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.services import rule_engine

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


@router.get("")
def list_versions():
    return {
        "active_version": settings.active_rule_version,
        "versions": [
            {
                "version": pack.version,
                "title": pack.title,
                "effective_date": pack.effective_date,
                "superseded_by": pack.superseded_by,
                "rule_count": len(pack.rules),
                "sha256": pack.rule_hash(),
            }
            for pack in rule_engine.list_rule_versions()
        ],
    }


@router.get("/diff")
def diff(
    from_version: str = Query(..., alias="from"),
    to_version: str = Query(..., alias="to"),
):
    try:
        return {
            "from": from_version,
            "to": to_version,
            "changes": rule_engine.diff_rule_versions(from_version, to_version),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{version}")
def get_version(version: str):
    try:
        pack = rule_engine.get_rule_pack(version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "version": pack.version,
        "title": pack.title,
        "effective_date": pack.effective_date,
        "superseded_by": pack.superseded_by,
        "sha256": pack.rule_hash(),
        "rules": pack.rules,
    }
