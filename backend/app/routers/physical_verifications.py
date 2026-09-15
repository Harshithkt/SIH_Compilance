"""API Router for Physical Verification (P0).

Handles physical sample weighing, unit normalization, LMPC Rule 22 MPE checks,
and evidence ledger commits.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, require_role
from app.services.physical_verification import record_physical_verification

router = APIRouter(prefix="/api/v1/physical-verifications", tags=["physical-verifications"])


@router.post("", response_model=schemas.PhysicalVerificationOut, status_code=status.HTTP_201_CREATED)
def create_physical_verification(
    payload: schemas.PhysicalVerificationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        verification = record_physical_verification(
            db=db,
            scan_id=payload.scan_id,
            officer_username=current_user.full_name or current_user.username,
            declared_quantity=payload.declared_quantity,
            declared_unit=payload.declared_unit,
            observed_quantity=payload.observed_quantity,
            observed_unit=payload.observed_unit,
            sample_number=payload.sample_number,
            notes=payload.notes,
            case_id=payload.case_id,
        )
        return verification
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/{verification_id}", response_model=schemas.PhysicalVerificationOut)
def get_physical_verification(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rec = db.query(models.PhysicalVerification).filter(models.PhysicalVerification.id == verification_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical verification record not found.")
    return rec


@router.get("/scan/{scan_id}", response_model=List[schemas.PhysicalVerificationOut])
def list_scan_verifications(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    records = (
        db.query(models.PhysicalVerification)
        .filter(models.PhysicalVerification.scan_id == scan_id)
        .order_by(models.PhysicalVerification.sample_number.asc())
        .all()
    )
    return records
