"""Seller/manufacturer risk scoring for the prioritised enforcement worklist.

One scan is a data point; the same importer contravening the same clause across many SKUs
is a case. Officers cannot review thousands of flags equally, so the queue is ordered by
severity-weighted, repeat-weighted risk rather than by recency.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Entity, Scan
from app.services.rule_engine import SEVERITY_WEIGHT

REPEAT_STEP = 0.15
RECENCY_WINDOW_DAYS = 30
RECENCY_BOOST = 1.1


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def score_entity(entity: Entity) -> dict:
    scans = entity.scans
    violations = [v for scan in scans for v in scan.violations]
    violating_scans = [s for s in scans if s.violations]

    base = sum(SEVERITY_WEIGHT.get(v.severity, 1) for v in violations)
    repeat_multiplier = 1 + REPEAT_STEP * max(0, len(violating_scans) - 1)

    latest_scan = max(scans, key=lambda s: _as_utc(s.captured_at), default=None)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=RECENCY_WINDOW_DAYS)
    recency = (
        RECENCY_BOOST
        if any(_as_utc(s.captured_at) >= recent_cutoff for s in violating_scans)
        else 1.0
    )

    clause_counts: dict[str, int] = {}
    for viol in violations:
        clause_counts[viol.clause] = clause_counts.get(viol.clause, 0) + 1

    return {
        "entity": entity,
        "scan_count": len(scans),
        "violation_count": len(violations),
        "high_severity_count": sum(1 for v in violations if v.severity == "high"),
        "risk_score": round(base * repeat_multiplier * recency, 1),
        "repeat_offender": len(violating_scans) >= 2,
        "latest_verdict": latest_scan.verdict if latest_scan else None,
        "latest_scan_at": _as_utc(latest_scan.captured_at) if latest_scan else None,
        "top_clauses": sorted(clause_counts.items(), key=lambda kv: -kv[1])[:3],
    }


def build_worklist(db: Session, limit: int = 50) -> list[dict]:
    entities = (
        db.execute(
            select(Entity).options(
                selectinload(Entity.scans).selectinload(Scan.violations)
            )
        )
        .scalars()
        .all()
    )
    scored = [score_entity(entity) for entity in entities]
    scored.sort(key=lambda item: (-item["risk_score"], -item["high_severity_count"]))
    return scored[:limit]
