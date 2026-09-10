from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Declaration, ManualOverride, Scan
from app.schemas import OverrideIn, OverrideOut, ScanOut, ScanSummaryOut
from app.services import evidence_chain, extraction, nebius, pipeline, rule_engine

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


def _load_scan(db: Session, scan_id: str) -> Scan:
    scan = db.execute(
        select(Scan)
        .options(
            selectinload(Scan.declarations),
            selectinload(Scan.violations),
            selectinload(Scan.ledger_entry),
            selectinload(Scan.entity),
        )
        .where(Scan.id == scan_id)
    ).scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.post("", response_model=dict, status_code=201)
async def create_scan(
    image: UploadFile = File(...),
    officer_name: str = Form(...),
    lang: str = Form("en"),
    product_name: str | None = Form(None),
    gps_lat: float | None = Form(None),
    gps_lon: float | None = Form(None),
    is_food_item: bool = Form(False),
    is_imported: bool = Form(False),
    rule_version: str | None = Form(None),
    provider: str | None = Form(None),
    raw_text: str | None = Form(None),
    skip_quality_gate: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Capture a label, evaluate it, and commit the result to the evidence ledger."""
    image_path, image_hash = pipeline.store_image(image.file, image.filename or "capture.jpg")

    try:
        scan, quality_report = pipeline.run_scan(
            db,
            image_path=image_path,
            image_sha256=image_hash,
            officer_name=officer_name,
            lang=lang,
            provider_preference=provider,
            raw_text=raw_text,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            product_name=product_name,
            is_food_item=is_food_item,
            is_imported=is_imported,
            rule_version=rule_version,
            skip_quality_gate=skip_quality_gate,
        )
    except pipeline.QualityGateRejected as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "capture_quality_rejected",
                "message": "This frame is not good enough to be used as evidence. Retake the photo.",
                **exc.report.as_dict(),
            },
        ) from exc
    except nebius.NebiusError as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=502, detail={"error": "vision_provider_failed", "message": str(exc)}
        ) from exc

    return {
        "scan": ScanOut.model_validate(scan).model_dump(mode="json"),
        "quality": quality_report,
    }


@router.get("", response_model=list[ScanSummaryOut])
def list_scans(
    verdict: str | None = Query(None),
    entity_id: str | None = Query(None),
    q: str | None = Query(None, description="Search by product name"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Scan).order_by(Scan.captured_at.desc()).limit(limit)
    if verdict:
        stmt = stmt.where(Scan.verdict == verdict)
    if entity_id:
        stmt = stmt.where(Scan.entity_id == entity_id)
    if q:
        stmt = stmt.where(Scan.product_name.ilike(f"%{q}%"))
    return db.execute(stmt).scalars().all()


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    return _load_scan(db, scan_id)


@router.get("/{scan_id}/image")
def get_scan_image(scan_id: str, db: Session = Depends(get_db)):
    scan = _load_scan(db, scan_id)
    path = Path(scan.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence image is no longer on disk")
    return FileResponse(path)


@router.post("/{scan_id}/overrides", response_model=OverrideOut, status_code=201)
def create_override(scan_id: str, payload: OverrideIn, db: Session = Depends(get_db)):
    """Officer correction to an extracted field.

    The correction is logged with its reason and the scan is re-evaluated against the
    rule version originally applied, then re-committed to the ledger — so the audit
    trail shows both what the machine read and what the officer certified.
    """
    scan = _load_scan(db, scan_id)
    declaration = db.get(Declaration, payload.declaration_id)
    if not declaration or declaration.scan_id != scan_id:
        raise HTTPException(status_code=404, detail="Declaration not found on this scan")

    override = ManualOverride(
        scan_id=scan_id,
        declaration_id=declaration.id,
        officer_name=payload.officer_name,
        old_value=declaration.value,
        new_value=payload.new_value,
        reason=payload.reason,
    )
    db.add(override)

    declaration.value = payload.new_value
    declaration.present = bool(payload.new_value.strip())
    declaration.status = "officer_verified"
    db.flush()

    _reevaluate(db, scan)
    db.commit()
    db.refresh(override)
    return override


def _reevaluate(db: Session, scan: Scan) -> None:
    rule_pack = rule_engine.get_rule_pack(scan.rule_version)
    declarations = {
        d.field: rule_engine.Declaration(
            field=d.field,
            value=d.value,
            present=d.present,
            height_px=d.height_px,
            bbox=d.bbox,
        )
        for d in scan.declarations
    }
    verdict = rule_engine.evaluate(
        rule_pack,
        declarations,
        {"is_food_item": scan.is_food_item, "is_imported": scan.is_imported},
    )

    from app.models import Violation

    for existing in list(scan.violations):
        db.delete(existing)
    db.flush()
    for viol in verdict.violations:
        db.add(Violation(scan_id=scan.id, **viol))
    scan.verdict = verdict.result
    scan.not_assessed = verdict.not_assessed
    db.flush()
    db.refresh(scan)
    evidence_chain.append_scan(db, scan)


@router.get("/{scan_id}/overrides", response_model=list[OverrideOut])
def list_overrides(scan_id: str, db: Session = Depends(get_db)):
    return (
        db.execute(
            select(ManualOverride)
            .where(ManualOverride.scan_id == scan_id)
            .order_by(ManualOverride.created_at.desc())
        )
        .scalars()
        .all()
    )


@router.get("/{scan_id}/rule-diff")
def rule_diff(
    scan_id: str,
    target_version: str = Query(..., description="Rule version to compare against"),
    db: Session = Depends(get_db),
):
    """Re-run this scan's declarations against a different rule version.

    Answers the question that actually arises in contested cases: which rules applied on
    the inspection date, and would today's rules produce a different verdict?
    """
    scan = _load_scan(db, scan_id)
    try:
        target_pack = rule_engine.get_rule_pack(target_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    declarations = {
        d.field: rule_engine.Declaration(
            field=d.field, value=d.value, present=d.present, height_px=d.height_px, bbox=d.bbox
        )
        for d in scan.declarations
    }
    recomputed = rule_engine.evaluate(
        target_pack,
        declarations,
        {"is_food_item": scan.is_food_item, "is_imported": scan.is_imported},
    )

    return {
        "scan_id": scan.id,
        "pinned_version": scan.rule_version,
        "pinned_verdict": scan.verdict,
        "target_version": target_version,
        "target_verdict": recomputed.result,
        "verdict_changed": recomputed.result != scan.verdict,
        "rule_changes": rule_engine.diff_rule_versions(scan.rule_version, target_version),
        "target_violations": recomputed.violations,
        "note": (
            "The pinned verdict remains the record of this inspection. This comparison is "
            "advisory only and does not alter the committed evidence."
        ),
    }


@router.post("/{scan_id}/violations/{violation_id}/explain")
def explain_violation(
    scan_id: str,
    violation_id: str,
    lang: str = Query("en", pattern="^(en|hi)$"),
    db: Session = Depends(get_db),
):
    """Plain-language explanation of one finding, for the officer and the shopkeeper.

    Advisory text only — the finding itself comes from the deterministic rule engine.
    """
    scan = _load_scan(db, scan_id)
    violation = next((v for v in scan.violations if v.id == violation_id), None)
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found on this scan")

    declaration = next((d for d in scan.declarations if d.field == violation.field), None)
    try:
        text = nebius.explain_violation(
            {
                "clause": violation.clause,
                "title": violation.title,
                "message": violation.message,
            },
            declaration.value if declaration else None,
            lang=lang,
        )
    except nebius.NebiusError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "violation_id": violation_id,
        "lang": lang,
        "explanation": text,
        "source": "llm_advisory",
        "note": "Advisory explanation. The finding and clause citation come from the rule engine.",
    }
