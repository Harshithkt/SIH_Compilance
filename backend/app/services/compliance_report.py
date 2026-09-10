"""Periodic compliance report for the ministry / controller of Legal Metrology.

Aggregates inspections over a period into the numbers an enforcement office is actually
asked for: how many inspections, what proportion contravened, which clauses fail most
often, and which entities account for the risk. Every figure comes from committed ledger
records, and the report states the integrity status of the chain it was drawn from.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Entity, Scan
from app.services import evidence_chain, risk_scoring


def period_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year, month, monthrange(year, month)[1], 23, 59, 59, tzinfo=timezone.utc)
    return start, end


def build_report(db: Session, year: int, month: int) -> dict:
    start, end = period_bounds(year, month)

    scans = (
        db.execute(
            select(Scan)
            .options(selectinload(Scan.violations), selectinload(Scan.entity))
            .where(Scan.captured_at >= start, Scan.captured_at <= end)
            .order_by(Scan.captured_at)
        )
        .scalars()
        .all()
    )

    verdicts = {"GO": 0, "FIX": 0, "REVIEW": 0}
    clause_counts: dict[str, dict] = {}
    officer_counts: dict[str, int] = {}
    entity_findings: dict[str, int] = {}
    rule_versions: dict[str, int] = {}

    for scan in scans:
        verdicts[scan.verdict] = verdicts.get(scan.verdict, 0) + 1
        officer_counts[scan.officer_name] = officer_counts.get(scan.officer_name, 0) + 1
        rule_versions[scan.rule_version] = rule_versions.get(scan.rule_version, 0) + 1

        for violation in scan.violations:
            record = clause_counts.setdefault(
                violation.clause, {"clause": violation.clause, "title": violation.title, "count": 0}
            )
            record["count"] += 1
            if scan.entity_id:
                entity_findings[scan.entity_id] = entity_findings.get(scan.entity_id, 0) + 1

    non_compliant = verdicts.get("FIX", 0) + verdicts.get("REVIEW", 0)
    total_findings = sum(record["count"] for record in clause_counts.values())

    worst_entities = []
    if entity_findings:
        entities = (
            db.execute(
                select(Entity)
                .options(selectinload(Entity.scans).selectinload(Scan.violations))
                .where(Entity.id.in_(entity_findings))
            )
            .scalars()
            .all()
        )
        scored = [risk_scoring.score_entity(entity) for entity in entities]
        scored.sort(key=lambda item: -item["risk_score"])
        worst_entities = [
            {
                "name": item["entity"].name,
                "address": item["entity"].address,
                "risk_score": item["risk_score"],
                "findings_in_period": entity_findings.get(item["entity"].id, 0),
                "repeat_offender": item["repeat_offender"],
            }
            for item in scored[:10]
        ]

    return {
        "period": {
            "year": year,
            "month": month,
            "label": start.strftime("%B %Y"),
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
        "totals": {
            "inspections": len(scans),
            "non_compliant": non_compliant,
            "non_compliance_rate": round(non_compliant / len(scans), 3) if scans else 0.0,
            "findings": total_findings,
            "entities_with_findings": len(entity_findings),
        },
        "verdicts": verdicts,
        "rule_versions_applied": rule_versions,
        "inspections_by_officer": [
            {"officer": officer, "inspections": count}
            for officer, count in sorted(officer_counts.items(), key=lambda kv: -kv[1])
        ],
        "clause_breakdown": sorted(
            clause_counts.values(), key=lambda record: -record["count"]
        ),
        "priority_entities": worst_entities,
        "evidence_integrity": evidence_chain.verify_chain(db),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Figures are drawn from inspections committed to the evidence ledger. The "
            "integrity status above reports whether those records still verify against "
            "the hashes recorded at inspection time."
        ),
    }
