"""Case lifecycle: officer decision -> case -> escalation -> closure -> audit record.

The rule engine's verdict is the AI's finding. It is never overwritten by review — an
officer's decision is a separate, later fact, recorded on the scan and logged append-only
in ScanReview so a re-review does not erase the first one. Only a *confirmed* FIX or
REVIEW opens a case; a rejected finding never becomes a case, and an unreviewed finding
is not yet official at all.

A case is classified by severity into one of two tracks, each with its own response
window: a minor (FIX) finding gets a correction notice, a serious (REVIEW) finding opens
a formal case. Every open case has an owner and a due date. There is no background
scheduler in this deployment, so overdue cases are escalated lazily — checked and flipped
whenever cases are listed or the worklist/report is built — rather than left to silently
expire. Closing a case (resolved or unresolved) writes the outcome to the audit record
with the evidence hash and rule version current at that moment, and — if the case had
been escalated — carries the supervisor's countersignature alongside the officer's.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Case, Scan, ScanReview

DECISIONS = ("confirmed", "rejected", "needs_more_evidence")
TRACK_BY_VERDICT = {"FIX": "correction_notice", "REVIEW": "formal_case"}
OPEN_STATUSES = ("open", "escalated")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def response_days_for(track: str) -> int:
    return (
        settings.formal_case_response_days
        if track == "formal_case"
        else settings.correction_notice_response_days
    )


def worst_severity(scan: Scan) -> str:
    severities = {v.severity for v in scan.violations}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def open_case(db: Session, scan: Scan, officer_name: str) -> Case:
    """Open (or reopen) the case for a confirmed FIX/REVIEW scan.

    A scan carries at most one case. If a prior case on this scan was already closed —
    the officer corrected the label and the rule engine now finds a fresh contravention,
    for instance — re-confirming opens a new response window on the same case record
    rather than losing the history of the first one.
    """
    track = TRACK_BY_VERDICT.get(scan.verdict, "correction_notice")
    days = response_days_for(track)
    now = _now()

    case = scan.case
    if case is None:
        case = Case(scan_id=scan.id, entity_id=scan.entity_id)
        db.add(case)

    case.track = track
    case.severity = worst_severity(scan)
    case.status = "open"
    case.officer_name = officer_name
    case.rule_version = scan.rule_version
    case.opened_at = now
    case.due_at = now + timedelta(days=days)
    case.response_days = days
    case.escalated_at = None
    case.escalated_to = None
    case.closed_at = None
    case.closed_by = None
    case.resolution_notes = None
    case.evidence_hash_at_close = None
    case.countersigned_by = None
    db.flush()
    return case


def submit_decision(
    db: Session,
    scan: Scan,
    *,
    officer_name: str,
    decision: str,
    notes: str | None = None,
) -> Scan:
    """Record the officer's decision on this scan's verdict — the fact that becomes
    official, kept separate from (and never overwriting) the AI's own finding."""
    if decision not in DECISIONS:
        raise ValueError(f"Unknown decision: {decision}")

    scan.officer_decision = decision
    scan.officer_decision_by = officer_name
    scan.officer_decision_at = _now()
    scan.officer_decision_notes = notes
    db.add(
        ScanReview(scan_id=scan.id, officer_name=officer_name, decision=decision, notes=notes)
    )
    db.flush()

    if decision == "confirmed" and scan.verdict in TRACK_BY_VERDICT:
        open_case(db, scan, officer_name)
    elif decision == "rejected" and scan.case and scan.case.status in OPEN_STATUSES:
        # The officer determined the underlying finding does not stand — the case
        # closes with that determination rather than being left open or escalating.
        scan.case.status = "rejected"
        scan.case.closed_at = _now()
        scan.case.closed_by = officer_name
        scan.case.resolution_notes = notes or "Finding rejected on officer review."

    db.commit()
    db.refresh(scan)
    return scan


def escalate_overdue(db: Session) -> int:
    """Flip every open case past its due date to escalated. Called at the top of every
    endpoint that lists or scores cases, so escalation state is always current without
    a background job."""
    overdue = (
        db.execute(select(Case).where(Case.status == "open", Case.due_at < _now()))
        .scalars()
        .all()
    )
    for case in overdue:
        case.status = "escalated"
        case.escalated_at = _now()
        case.escalated_to = settings.supervisor_role_name
    if overdue:
        db.commit()
    return len(overdue)


def close_case(
    db: Session,
    case: Case,
    *,
    closed_by: str,
    resolution: str,
    notes: str | None = None,
) -> Case:
    """Close a case as resolved (the seller corrected it) or unresolved (they did not).

    If the case had already been escalated, the closing officer's name stands alongside
    the original owner's as a countersignature — the dual-signatory record an escalated
    finding warrants."""
    if resolution not in ("resolved", "unresolved"):
        raise ValueError("resolution must be 'resolved' or 'unresolved'")

    was_escalated = case.status == "escalated"
    case.status = resolution
    case.closed_at = _now()
    case.closed_by = closed_by
    case.resolution_notes = notes
    case.evidence_hash_at_close = (
        case.scan.ledger_entry.entry_hash if case.scan and case.scan.ledger_entry else None
    )
    if was_escalated:
        case.countersigned_by = closed_by
    db.commit()
    db.refresh(case)
    return case


def counted_violations(scan: Scan) -> list:
    """Violations that count toward the seller's pattern history (worklist risk score,
    monthly-report findings) — only once an officer has confirmed the finding *and* its
    response window has closed without the seller correcting it in time (escalated or
    closed unresolved). An unreviewed AI finding, or one still within its response
    window, is not yet a strike against the seller: they have not been given, or have
    not yet had, the chance to respond that the case workflow promises them."""
    if scan.officer_decision != "confirmed":
        return []
    case = scan.case
    if not case or case.status not in ("escalated", "unresolved"):
        return []
    return list(scan.violations)
