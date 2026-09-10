from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import LedgerEntry, Scan
from app.schemas import LedgerVerifyOut
from app.services import docket_pdf, evidence_chain

router = APIRouter(prefix="/api/v1", tags=["evidence"])


@router.get("/ledger")
def list_ledger(limit: int = 200, db: Session = Depends(get_db)):
    entries = (
        db.execute(
            select(LedgerEntry)
            .options(selectinload(LedgerEntry.scan))
            .order_by(LedgerEntry.sequence.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "sequence": e.sequence,
            "scan_id": e.scan_id,
            "prev_hash": e.prev_hash,
            "payload_hash": e.payload_hash,
            "entry_hash": e.entry_hash,
            "created_at": e.created_at,
            "verdict": e.payload.get("verdict"),
            "officer_name": e.payload.get("officer_name"),
            "is_amendment": bool(e.scan and e.scan.ledger_entries and e.scan.ledger_entries[0].sequence != e.sequence),
        }
        for e in entries
    ]


@router.get("/ledger/verify", response_model=LedgerVerifyOut)
def verify_ledger(db: Session = Depends(get_db)):
    """Recompute the entire chain, including the on-disk hash of every evidence image.

    This is the live demonstration of tamper-evidence: modify a stored photo or a scan
    record and this endpoint names the exact ledger entry at which the record diverges.
    """
    return evidence_chain.verify_chain(db)


@router.get("/scans/{scan_id}/docket")
def get_docket(scan_id: str, db: Session = Depends(get_db)):
    """Generate (or regenerate) the prosecution evidence docket for one scan."""
    scan = db.execute(
        select(Scan)
        .options(
            selectinload(Scan.declarations),
            selectinload(Scan.violations),
            selectinload(Scan.ledger_entries),
            selectinload(Scan.entity),
        )
        .where(Scan.id == scan_id)
    ).scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    path = docket_pdf.build_docket(scan)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"LabelLens_Docket_{scan.id[:8].upper()}.pdf",
    )
