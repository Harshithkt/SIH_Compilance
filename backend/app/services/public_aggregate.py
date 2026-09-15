"""Public Aggregate Statistics Service.

Computes anonymized, aggregated compliance metrics for public transparency.
STRICT PRIVACY: Excludes seller names, officer names, case IDs, PII, and evidence images.
Calculates compliance rate with an explicit denominator, excluding REVIEW / NOT_ASSESSABLE.
"""

from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app import models


def get_public_aggregate_metrics(
    db: Session,
    district_filter: str | None = None,
    category_filter: str | None = None,
) -> Dict[str, Any]:
    scans = db.query(models.Scan).all()

    total_scans = len(scans)
    compliant_count = 0
    non_compliant_count = 0
    review_count = 0

    # Aggregate buckets by district & category
    district_stats: Dict[str, Dict[str, int]] = {}
    category_stats: Dict[str, Dict[str, int]] = {}

    for scan in scans:
        verdict = scan.verdict.upper() if scan.verdict else "REVIEW"
        
        # Categorize verdict
        if verdict in ("PASS", "COMPLIANT"):
            v_type = "compliant"
            compliant_count += 1
        elif verdict in ("FAIL", "NON_COMPLIANT", "FIX"):
            v_type = "non_compliant"
            non_compliant_count += 1
        else:
            v_type = "review"
            review_count += 1

        # District mapping (mocked/derived from GPS or default)
        district = "Chennai Central" if (scan.gps_lat or 0) > 13.0 else "Coimbatore Urban"
        category = "Pre-Packaged Food" if scan.is_food_item else "General Packaged Commodity"

        if district_filter and district_filter.lower() not in district.lower():
            continue
        if category_filter and category_filter.lower() not in category.lower():
            continue

        # Accumulate District Stats
        if district not in district_stats:
            district_stats[district] = {"total": 0, "compliant": 0, "non_compliant": 0, "review": 0}
        district_stats[district]["total"] += 1
        district_stats[district][v_type] += 1

        # Accumulate Category Stats
        if category not in category_stats:
            category_stats[category] = {"total": 0, "compliant": 0, "non_compliant": 0, "review": 0}
        category_stats[category]["total"] += 1
        category_stats[category][v_type] += 1

    # Calculate overall compliance rate (Denominator = compliant + non_compliant)
    valid_evaluations = compliant_count + non_compliant_count
    overall_rate = round((compliant_count / valid_evaluations * 100.0), 1) if valid_evaluations > 0 else 0.0

    # Format District Output
    district_list: List[Dict[str, Any]] = []
    for dist_name, d_data in district_stats.items():
        d_valid = d_data["compliant"] + d_data["non_compliant"]
        d_rate = round((d_data["compliant"] / d_valid * 100.0), 1) if d_valid > 0 else 0.0
        district_list.append({
            "district": dist_name,
            "total_inspections": d_data["total"],
            "compliant_count": d_data["compliant"],
            "non_compliant_count": d_data["non_compliant"],
            "review_count": d_data["review"],
            "compliance_rate_percent": d_rate,
        })

    # Format Category Output
    category_list: List[Dict[str, Any]] = []
    for cat_name, c_data in category_stats.items():
        c_valid = c_data["compliant"] + c_data["non_compliant"]
        c_rate = round((c_data["compliant"] / c_valid * 100.0), 1) if c_valid > 0 else 0.0
        category_list.append({
            "category": cat_name,
            "total_inspections": c_data["total"],
            "compliant_count": c_data["compliant"],
            "non_compliant_count": c_data["non_compliant"],
            "review_count": c_data["review"],
            "compliance_rate_percent": c_rate,
        })

    return {
        "total_inspections": total_scans,
        "compliant_count": compliant_count,
        "non_compliant_count": non_compliant_count,
        "review_count": review_count,
        "compliance_rate_percent": overall_rate,
        "districts": district_list,
        "categories": category_list,
        "disclaimer": "Anonymized aggregate inspection metrics for public transparency. Contains no entity, seller, officer, or case-level PII.",
    }
