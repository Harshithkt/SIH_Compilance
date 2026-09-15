"""Historical Enforcement Signal Service.

Generates informational history indicators based on prior entity inspection records.
Does NOT make a legal determination or label entities as "repeat offenders".
"""

from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session

from app import models


def get_historical_enforcement_signal(db: Session, entity_id: str) -> Dict[str, Any]:
    entity = db.query(models.Entity).filter(models.Entity.id == entity_id).first()
    if not entity:
        return {
            "entity_id": entity_id,
            "entity_name": "Unknown Entity",
            "total_cases": 0,
            "adverse_cases": 0,
            "repeat_count": 0,
            "signal_level": "NO_PRIOR_ADVERSE",
            "display_message": "History signal: No prior recorded adverse finding found.",
            "disclaimer": "Informational enforcement signal — not a legal determination.",
        }

    cases = (
        db.query(models.Case)
        .filter(models.Case.entity_id == entity_id)
        .all()
    )

    adverse_cases = [c for c in cases if c.status in ("open", "escalated", "unresolved")]
    adverse_count = len(adverse_cases)

    if adverse_count == 0:
        signal_level = "NO_PRIOR_ADVERSE"
        msg = "No prior recorded adverse finding found."
    elif adverse_count == 1:
        signal_level = "PRIOR_ADVERSE_EXISTS"
        msg = "Previous adverse inspection records exist."
    else:
        signal_level = "REPEAT_HISTORY_INDICATED"
        msg = "Repeat-history signal — officer/supervisor review required."

    return {
        "entity_id": entity.id,
        "entity_name": entity.name,
        "total_cases": len(cases),
        "adverse_cases": adverse_count,
        "repeat_count": adverse_count,
        "signal_level": signal_level,
        "display_message": msg,
        "disclaimer": "Informational enforcement signal — not a legal determination.",
    }
