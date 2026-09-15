"""API Router for Public Transparency Dashboard (P2).

Publicly accessible aggregate statistics endpoint. Does not require authentication.
Exposes strictly anonymized metrics with zero PII or seller identity.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services.public_aggregate import get_public_aggregate_metrics

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/aggregate", response_model=schemas.PublicAggregateOut)
def get_public_aggregate(
    district: Optional[str] = Query(None, description="Optional district name filter"),
    category: Optional[str] = Query(None, description="Optional product category filter"),
    db: Session = Depends(get_db),
):
    result = get_public_aggregate_metrics(db, district_filter=district, category_filter=category)
    return result
