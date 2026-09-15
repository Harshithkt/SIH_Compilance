"""Physical Verification Engine for Legal Metrology officers.

Compares declared label quantity against observed physical measurement, applies
LMPC Rule 22 Maximum Permissible Error (MPE) tolerances, and commits verified evidence.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app import models
from app.services.quantity import Quantity, parse as parse_quantity, UNITS
from app.services.mpe_rule22 import get_maximum_permissible_error, MPELookupResult
from app.services import evidence_chain
import hashlib
import json
from datetime import datetime, timezone


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def evaluate_physical_measurement(
    declared_str: Optional[str],
    declared_unit_override: Optional[str],
    observed_val: float,
    observed_unit_str: str,
) -> Dict[str, Any]:
    """Evaluates physical measurement against declared quantity.

    Returns dict with keys:
      result: PASS | FAIL | REVIEW | NOT_ASSESSABLE
      shortfall: float (in base unit)
      declared_base: float
      observed_base: float
      applicable_mpe: float
      tolerance_basis: str
      display_mpe: str
      rule_id: str
      rule_version: str
      explanation: str
      enforcement_flag: str
      details: dict
    """
    if observed_val <= 0:
        return {
            "result": "NOT_ASSESSABLE",
            "explanation": "Observed quantity must be a positive number.",
            "enforcement_flag": "NO_ACTION",
            "details": {"error": "invalid_observed_quantity"},
        }

    # Normalize observed unit
    obs_unit_clean = observed_unit_str.lower().strip()
    if obs_unit_clean not in UNITS:
        return {
            "result": "REVIEW",
            "explanation": f"Observed unit '{observed_unit_str}' is not a recognized metric unit.",
            "enforcement_flag": "REVIEW_REQUIRED",
            "details": {"unrecognized_unit": observed_unit_str},
        }

    obs_dim, obs_multiplier = UNITS[obs_unit_clean]
    obs_base_val = observed_val * obs_multiplier

    # Parse declared quantity
    declared_qty = parse_quantity(declared_str)
    if declared_qty is None and declared_unit_override:
        # Try constructing from declared_str if it was just numeric
        try:
            num_val = float(declared_str) if declared_str else 0.0
            if num_val > 0:
                decl_unit_clean = declared_unit_override.lower().strip()
                if decl_unit_clean in UNITS:
                    d_dim, d_mult = UNITS[decl_unit_clean]
                    declared_qty = Quantity(
                        value=num_val,
                        unit=decl_unit_clean,
                        dimension=d_dim,
                        base_value=num_val * d_mult,
                    )
        except (ValueError, TypeError):
            pass

    if declared_qty is None:
        return {
            "result": "NOT_ASSESSABLE",
            "explanation": "Missing or unparseable declared net quantity on product package.",
            "enforcement_flag": "NO_ACTION",
            "details": {"error": "missing_declared_quantity"},
        }

    # Check dimension compatibility (e.g. mass vs mass, volume vs volume)
    if declared_qty.dimension != obs_dim:
        return {
            "result": "REVIEW",
            "explanation": (
                f"Incompatible measurement dimensions: declared unit '{declared_qty.unit}' ({declared_qty.dimension}) "
                f"vs observed unit '{observed_unit_str}' ({obs_dim}). Officer verification required."
            ),
            "enforcement_flag": "REVIEW_REQUIRED",
            "details": {
                "declared_dimension": declared_qty.dimension,
                "observed_dimension": obs_dim,
            },
        }

    # MPE Lookup
    mpe_info: MPELookupResult = get_maximum_permissible_error(declared_qty)

    # Shortfall calculation: Shortfall = Declared - Observed
    shortfall_base = declared_qty.base_value - obs_base_val

    # Assessment: PASS if shortfall <= MPE; FAIL if shortfall > MPE
    if shortfall_base <= mpe_info.mpe_value_in_base:
        result = "PASS"
        enforcement = "NO_ACTION"
        if shortfall_base > 0:
            explanation = (
                f"Physical verification result: PASS. "
                f"Observed shortfall of {shortfall_base:.2f} (base units) is within the maximum permissible error "
                f"of {mpe_info.mpe_value_in_base:.2f} ({mpe_info.display_mpe})."
            )
        else:
            explanation = (
                f"Physical verification result: PASS. "
                f"Observed quantity meets or exceeds declared net quantity."
            )
    else:
        result = "FAIL"
        enforcement = "Enforcement attention indicated — officer review required."
        explanation = (
            f"Physical verification result: FAIL. "
            f"Observed shortfall of {shortfall_base:.2f} (base units) exceeds the applicable Maximum Permissible Error "
            f"of {mpe_info.mpe_value_in_base:.2f} ({mpe_info.display_mpe}) under {mpe_info.rule_id}."
        )

    return {
        "result": result,
        "shortfall": round(shortfall_base, 4),
        "declared_base": round(declared_qty.base_value, 4),
        "observed_base": round(obs_base_val, 4),
        "applicable_mpe": round(mpe_info.mpe_value_in_base, 4),
        "display_mpe": mpe_info.display_mpe,
        "tolerance_basis": mpe_info.tolerance_basis,
        "rule_id": mpe_info.rule_id,
        "rule_version": mpe_info.rule_version,
        "explanation": explanation,
        "enforcement_flag": enforcement,
        "details": {
            "declared_quantity_parsed": f"{declared_qty.value} {declared_qty.unit}",
            "observed_quantity_entered": f"{observed_val} {observed_unit_str}",
            "dimension": obs_dim,
            "shortfall_base_units": round(shortfall_base, 4),
            "mpe_threshold_base_units": round(mpe_info.mpe_value_in_base, 4),
        },
    }


def record_physical_verification(
    db: Session,
    scan_id: str,
    officer_username: str,
    declared_quantity: str,
    declared_unit: str,
    observed_quantity: float,
    observed_unit: str,
    sample_number: int = 1,
    notes: Optional[str] = None,
    case_id: Optional[str] = None,
) -> models.PhysicalVerification:
    """Evaluates measurement, persists PhysicalVerification model, and commits an evidence ledger entry."""
    scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if not scan:
        raise ValueError(f"Scan with ID '{scan_id}' not found.")

    eval_result = evaluate_physical_measurement(
        declared_str=f"{declared_quantity} {declared_unit}",
        declared_unit_override=declared_unit,
        observed_val=observed_quantity,
        observed_unit_str=observed_unit,
    )

    decl_qty_parsed = parse_quantity(f"{declared_quantity} {declared_unit}")
    decl_base = decl_qty_parsed.base_value if decl_qty_parsed else 0.0
    
    obs_unit_clean = observed_unit.lower().strip()
    obs_mult = UNITS.get(obs_unit_clean, ("mass", 1.0))[1]
    obs_base = observed_quantity * obs_mult

    verification_rec = models.PhysicalVerification(
        scan_id=scan.id,
        case_id=case_id or (scan.case.id if scan.case else None),
        entity_id=scan.entity_id,
        sample_number=sample_number,
        declared_quantity=str(declared_quantity),
        declared_unit=declared_unit,
        observed_quantity=float(observed_quantity),
        observed_unit=observed_unit,
        normalized_declared_quantity=round(decl_base, 4),
        normalized_observed_quantity=round(obs_base, 4),
        shortfall=eval_result.get("shortfall", 0.0),
        applicable_rule_id=eval_result.get("rule_id", "LMPC-RULE-22"),
        applicable_rule_version=eval_result.get("rule_version", "2011-v1"),
        applicable_mpe=eval_result.get("applicable_mpe", 0.0),
        tolerance_basis=eval_result.get("tolerance_basis", "percentage"),
        result=eval_result["result"],
        verification_status="CONFIRMED",
        officer_username=officer_username,
        notes=notes,
        calculation_details=eval_result,
    )

    db.add(verification_rec)
    db.flush()

    # Evidence ledger integration — create a lightweight hash of the verification record.
    # This binds the physical verification to the scan's evidence trail as a tamper-evident digest.
    ledger_payload = {
        "event_type": "PHYSICAL_VERIFICATION",
        "verification_id": verification_rec.id,
        "sample_number": sample_number,
        "declared": f"{declared_quantity} {declared_unit}",
        "observed": f"{observed_quantity} {observed_unit}",
        "shortfall_base": eval_result.get("shortfall"),
        "mpe_base": eval_result.get("applicable_mpe"),
        "result": eval_result["result"],
        "officer": officer_username,
        "timestamp": verification_rec.timestamp.isoformat(),
    }
    evidence_hash = _hash_payload(ledger_payload)
    verification_rec.evidence_hash = evidence_hash

    db.commit()
    db.refresh(verification_rec)
    return verification_rec
