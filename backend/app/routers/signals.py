"""API Router for Signals & Small Deterministic Checks (P1 & P2).

Exposes endpoints for price anomaly signals, contact syntax validation,
multi-unit consistency, and non-legal historical enforcement signals.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.services.price_anomaly import compute_price_anomaly_signal
from app.services.contact_validator import validate_contact_details
from app.services.multi_unit_consistency import check_multi_unit_consistency
from app.services.history_signal import get_historical_enforcement_signal

router = APIRouter(prefix="/api/v1", tags=["signals"])


@router.get("/price-signals/{scan_id}", response_model=schemas.PriceAnomalyOut)
def get_price_signal(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = compute_price_anomaly_signal(db, scan_id)
    return result


@router.get("/contact-validation/{scan_id}", response_model=schemas.ContactValidationOut)
def get_contact_validation(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = validate_contact_details(db, scan_id)
    return result


@router.get("/consistency-checks/{inspection_visit_id}", response_model=schemas.MultiUnitConsistencyOut)
def get_consistency_check(
    inspection_visit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = check_multi_unit_consistency(db, inspection_visit_id)
    return result


@router.get("/history-signals/{entity_id}", response_model=schemas.HistorySignalOut)
def get_history_signal(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = get_historical_enforcement_signal(db, entity_id)
    return result
