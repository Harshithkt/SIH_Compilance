from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, outranks, record_audit
from app.database import get_db
from app.models import Case, User
from app.schemas import CaseCloseIn, CaseOut
from app.services import case_engine

router = APIRouter(
    prefix="/api/v1/cases",
    tags=["cases"],
    dependencies=[Depends(get_current_user)],
)


def _load_case(db: Session, case_id: str) -> Case:
    case = db.execute(
        select(Case)
        .options(selectinload(Case.scan), selectinload(Case.entity))
        .where(Case.id == case_id)
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("", response_model=list[CaseOut])
def list_cases(
    status: str | None = Query(None, description="open | escalated | resolved | unresolved | rejected"),
    track: str | None = Query(None, description="correction_notice | formal_case"),
    entity_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Every case, escalating any that have passed their due date before listing them —
    there is no background scheduler in this deployment, so escalation is checked
    whenever a case is read rather than left to a timer."""
    case_engine.escalate_overdue(db)
    stmt = select(Case).options(selectinload(Case.scan), selectinload(Case.entity))
    if status:
        stmt = stmt.where(Case.status == status)
    if track:
        stmt = stmt.where(Case.track == track)
    if entity_id:
        stmt = stmt.where(Case.entity_id == entity_id)
    stmt = stmt.order_by(Case.due_at)
    return db.execute(stmt).scalars().all()


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case_engine.escalate_overdue(db)
    return _load_case(db, case_id)


@router.post("/{case_id}/close", response_model=CaseOut)
def close_case(
    case_id: str,
    payload: CaseCloseIn,
    db: Session = Depends(get_db),
    officer: User = Depends(get_current_user),
):
    """Close a case as resolved (the seller corrected it within the window) or
    unresolved (they did not). The outcome — including, if the case had escalated, the
    supervisor's countersignature — is what the docket and monthly report draw on, not
    the raw AI finding."""
    case = _load_case(db, case_id)
    if case.status not in ("open", "escalated"):
        raise HTTPException(status_code=409, detail=f"Case is already {case.status}")
    if payload.resolution not in ("resolved", "unresolved"):
        raise HTTPException(status_code=422, detail="resolution must be 'resolved' or 'unresolved'")
    # An escalated case is one the response window already ran out on: closing it is the
    # supervisor's call, and their name is what goes on the countersignature line.
    if case.status == "escalated" and not outranks(officer, "supervisor"):
        raise HTTPException(
            status_code=403,
            detail="This case has been escalated — only a supervisor can close it.",
        )

    case_engine.close_case(
        db,
        case,
        closed_by=officer.full_name,
        resolution=payload.resolution,
        notes=payload.notes,
    )
    record_audit(
        db,
        actor=officer,
        action="case.closed",
        target_type="case",
        target_id=case.id,
        detail={"resolution": payload.resolution},
    )
    db.commit()
    return _load_case(db, case_id)
