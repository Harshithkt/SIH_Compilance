"""Multi-Unit Declaration Consistency Service.

Compares net quantity, MRP, and commodity declarations across multiple product units
scanned during a single officer inspection visit.
"""

from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app import models


def check_multi_unit_consistency(db: Session, inspection_visit_id: str) -> Dict[str, Any]:
    scans = (
        db.query(models.Scan)
        .filter(models.Scan.inspection_visit_id == inspection_visit_id)
        .all()
    )

    if len(scans) < 2:
        return {
            "inspection_visit_id": inspection_visit_id,
            "unit_count": len(scans),
            "status": "INSUFFICIENT_EVIDENCE",
            "differing_declarations": [],
            "explanation": f"Fewer than 2 units recorded under inspection visit '{inspection_visit_id}'. Minimum 2 units required for multi-unit comparison.",
        }

    # Extract field maps per scan
    scan_declarations: List[Dict[str, str]] = []
    for index, scan in enumerate(scans, 1):
        fields = {"unit_label": f"Unit #{index} ({scan.id[:8]})"}
        for decl in scan.declarations:
            if decl.field and decl.value:
                fields[decl.field] = decl.value.strip()
        scan_declarations.append(fields)

    # Check consistency across keys
    keys_to_check = ["net_quantity", "mrp", "common_name", "product_name"]
    differing: List[Dict[str, Any]] = []

    for key in keys_to_check:
        values = set()
        details_by_unit = {}
        for item in scan_declarations:
            val = item.get(key)
            if val:
                values.add(val)
                details_by_unit[item["unit_label"]] = val

        if len(values) > 1:
            differing.append({
                "field": key,
                "detected_values": list(values),
                "breakdown": details_by_unit,
                "message": f"Declaration '{key}' varies across units: {', '.join(values)}"
            })

    if differing:
        status = "INCONSISTENT"
        explanation = f"Multi-unit declaration check: Found differences in {len(differing)} declared field(s) across {len(scans)} scanned units."
    else:
        status = "CONSISTENT"
        explanation = f"Multi-unit declaration check: Declarations are consistent across all {len(scans)} scanned units."

    return {
        "inspection_visit_id": inspection_visit_id,
        "unit_count": len(scans),
        "status": status,
        "differing_declarations": differing,
        "explanation": explanation,
    }
