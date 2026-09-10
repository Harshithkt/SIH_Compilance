from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Entity, Scan
from app.schemas import EntityOut, ScanSummaryOut
from app.services import compliance_report, risk_scoring

router = APIRouter(prefix="/api/v1", tags=["enforcement"])


@router.get("/worklist")
def get_worklist(limit: int = 50, db: Session = Depends(get_db)):
    """Risk-ranked enforcement queue: severity-weighted, repeat-offender-weighted."""
    items = risk_scoring.build_worklist(db, limit=limit)
    return [
        {
            "entity": EntityOut.model_validate(item["entity"]).model_dump(),
            "scan_count": item["scan_count"],
            "violation_count": item["violation_count"],
            "high_severity_count": item["high_severity_count"],
            "risk_score": item["risk_score"],
            "repeat_offender": item["repeat_offender"],
            "latest_verdict": item["latest_verdict"],
            "latest_scan_at": item["latest_scan_at"],
            "top_clauses": [
                {"clause": clause, "count": count} for clause, count in item["top_clauses"]
            ],
        }
        for item in items
    ]


@router.get("/entities/{entity_id}")
def get_entity(entity_id: str, db: Session = Depends(get_db)):
    entity = db.execute(
        select(Entity)
        .options(selectinload(Entity.scans).selectinload(Scan.violations))
        .where(Entity.id == entity_id)
    ).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    scored = risk_scoring.score_entity(entity)
    return {
        "entity": EntityOut.model_validate(entity).model_dump(),
        "risk_score": scored["risk_score"],
        "repeat_offender": scored["repeat_offender"],
        "scan_count": scored["scan_count"],
        "violation_count": scored["violation_count"],
        "high_severity_count": scored["high_severity_count"],
        "top_clauses": [
            {"clause": clause, "count": count} for clause, count in scored["top_clauses"]
        ],
        "scans": [
            ScanSummaryOut.model_validate(s).model_dump(mode="json")
            for s in sorted(entity.scans, key=lambda s: s.captured_at, reverse=True)
        ],
    }


@router.get("/reports/monthly")
def monthly_report(
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    """Periodic compliance report for the controller's office."""
    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = month or now.month
    if not 1 <= target_month <= 12:
        raise HTTPException(status_code=422, detail="month must be between 1 and 12")
    return compliance_report.build_report(db, target_year, target_month)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    scans = db.execute(select(Scan).options(selectinload(Scan.violations))).scalars().all()
    verdict_counts = {"GO": 0, "FIX": 0, "REVIEW": 0}
    clause_counts: dict[str, int] = {}
    for scan in scans:
        verdict_counts[scan.verdict] = verdict_counts.get(scan.verdict, 0) + 1
        for viol in scan.violations:
            clause_counts[viol.clause] = clause_counts.get(viol.clause, 0) + 1

    entity_count = db.execute(select(Entity)).scalars().all()
    return {
        "total_scans": len(scans),
        "verdicts": verdict_counts,
        "total_violations": sum(clause_counts.values()),
        "entities_tracked": len(entity_count),
        "top_clauses": [
            {"clause": clause, "count": count}
            for clause, count in sorted(clause_counts.items(), key=lambda kv: -kv[1])[:6]
        ],
    }
