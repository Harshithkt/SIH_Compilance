"""Consumer Care Contact Syntax Validator.

Validates phone number and email address syntax using deterministic patterns.
Does NOT claim that contact details are functional/fake — strictly checks syntax format.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app import models

PHONE_PATTERN = re.compile(
    r"^(?:\+?91[\-\s]?)?(?:[189]\d{3}[\-\s]?\d{6}|[6-9]\d{9}|1800[\-\s]?\d{3}[\-\s]?\d{3,4}|0\d{2,4}[\-\s]?\d{6,8})$"
)

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def validate_contact_details(db: Session, scan_id: str) -> Dict[str, Any]:
    scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if not scan:
        return {
            "scan_id": scan_id,
            "phone_status": "NOT_ASSESSABLE",
            "email_status": "NOT_ASSESSABLE",
            "disclaimer": "Syntax format validation only — does not confirm working contact status.",
        }

    phone_val: Optional[str] = None
    email_val: Optional[str] = None

    for decl in scan.declarations:
        if decl.field in ("consumer_care", "customer_care", "contact_details") and decl.value:
            # Extract phone candidate
            phone_m = re.search(r"(\+?\d[\d\-\s]{8,14}\d)", decl.value)
            if phone_m:
                phone_val = phone_m.group(0).strip()
            
            # Extract email candidate
            email_m = re.search(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", decl.value)
            if email_m:
                email_val = email_m.group(0).strip()

    # Evaluate Phone Syntax
    if not phone_val:
        phone_status = "NOT_ASSESSABLE"
        phone_msg = "No phone number detected in consumer care declaration."
    elif PHONE_PATTERN.match(phone_val):
        phone_status = "PASS"
        phone_msg = f"Consumer care phone format appears valid: '{phone_val}'."
    else:
        phone_status = "FAIL"
        phone_msg = f"Consumer care phone format appears invalid: '{phone_val}'."

    # Evaluate Email Syntax
    if not email_val:
        email_status = "NOT_ASSESSABLE"
        email_msg = "No email address detected in consumer care declaration."
    elif EMAIL_PATTERN.match(email_val):
        email_status = "PASS"
        email_msg = f"Consumer care email format appears valid: '{email_val}'."
    else:
        email_status = "FAIL"
        email_msg = f"Consumer care email format appears invalid: '{email_val}'."

    return {
        "scan_id": scan_id,
        "phone": phone_val,
        "phone_status": phone_status,
        "phone_message": phone_msg,
        "email": email_val,
        "email_status": email_status,
        "email_message": email_msg,
        "disclaimer": "Syntax format validation only — does not confirm working contact status.",
    }
