"""Internal Price-Anomaly Signal Engine.

Calculates price per unit using internal historical inspection observations only.
No external data or scraping. Explicitly marked as non-legal analytical signals.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app import models
from app.services.quantity import parse as parse_quantity


def compute_price_anomaly_signal(db: Session, scan_id: str) -> Dict[str, Any]:
    scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if not scan:
        return {
            "scan_id": scan_id,
            "signal": "INSUFFICIENT_HISTORY",
            "explanation": "Scan record not found.",
            "disclaimer": "Internal analytical signal — not a legal finding.",
        }

    # Extract price (mrp) and net quantity declarations from scan
    mrp_val: Optional[float] = None
    decl_qty_str: Optional[str] = None

    for decl in scan.declarations:
        if decl.field == "mrp" and decl.value:
            # extract numeric float from mrp string e.g. "Rs 250.00" -> 250.0
            import re
            m = re.search(r"[\d,]+(?:\.\d+)?", decl.value)
            if m:
                try:
                    mrp_val = float(m.group(0).replace(",", ""))
                except ValueError:
                    pass
        elif decl.field in ("net_quantity", "quantity") and decl.value:
            decl_qty_str = decl.value

    qty_parsed = parse_quantity(decl_qty_str) if decl_qty_str else None

    if not mrp_val or not qty_parsed or qty_parsed.base_value <= 0:
        return {
            "scan_id": scan_id,
            "product_name": scan.product_name,
            "category": "Packaged Goods",
            "price": mrp_val,
            "declared_quantity": decl_qty_str,
            "unit_price": None,
            "historical_avg_unit_price": None,
            "historical_sample_count": 0,
            "signal": "INSUFFICIENT_HISTORY",
            "explanation": "Insufficient price or quantity declaration data on this scan to compute unit price.",
            "disclaimer": "Internal analytical signal — not a legal finding.",
        }

    current_unit_price = mrp_val / qty_parsed.base_value

    # Gather internal historical scans in same category/dimension
    historical_scans = (
        db.query(models.Scan)
        .filter(models.Scan.id != scan_id)
        .all()
    )

    historical_unit_prices: List[float] = []
    for h_scan in historical_scans:
        h_mrp: Optional[float] = None
        h_qty_str: Optional[str] = None
        for d in h_scan.declarations:
            if d.field == "mrp" and d.value:
                import re
                m = re.search(r"[\d,]+(?:\.\d+)?", d.value)
                if m:
                    try:
                        h_mrp = float(m.group(0).replace(",", ""))
                    except ValueError:
                        pass
            elif d.field in ("net_quantity", "quantity") and d.value:
                h_qty_str = d.value
        
        h_parsed = parse_quantity(h_qty_str) if h_qty_str else None
        if h_mrp and h_parsed and h_parsed.dimension == qty_parsed.dimension and h_parsed.base_value > 0:
            historical_unit_prices.append(h_mrp / h_parsed.base_value)

    if len(historical_unit_prices) < 3:
        return {
            "scan_id": scan_id,
            "product_name": scan.product_name,
            "category": f"Packaged Goods ({qty_parsed.dimension})",
            "price": mrp_val,
            "declared_quantity": decl_qty_str,
            "unit_price": round(current_unit_price, 4),
            "historical_avg_unit_price": round(statistics.mean(historical_unit_prices), 4) if historical_unit_prices else None,
            "historical_sample_count": len(historical_unit_prices),
            "signal": "INSUFFICIENT_HISTORY",
            "explanation": f"Insufficient historical internal inspection records (found {len(historical_unit_prices)}, minimum 3 required).",
            "disclaimer": "Internal analytical signal — not a legal finding.",
        }

    mean_price = statistics.mean(historical_unit_prices)
    stdev_price = statistics.stdev(historical_unit_prices) if len(historical_unit_prices) > 1 else 0.0

    if stdev_price > 0 and current_unit_price > (mean_price + 2.0 * stdev_price):
        signal = "REVIEW"
        explanation = (
            f"Price anomaly signal: Current unit price ({current_unit_price:.4f}/base unit) is significantly higher "
            f"than historical internal average ({mean_price:.4f}/base unit, std dev {stdev_price:.4f})."
        )
    elif stdev_price > 0 and current_unit_price > (mean_price + 1.0 * stdev_price):
        signal = "LOW_SIGNAL"
        explanation = (
            f"Price anomaly signal: Current unit price is slightly elevated compared to internal historical average."
        )
    else:
        signal = "NO_SIGNAL"
        explanation = "Price per unit is within normal expected historical range based on internal inspection data."

    return {
        "scan_id": scan_id,
        "product_name": scan.product_name,
        "category": f"Packaged Goods ({qty_parsed.dimension})",
        "price": mrp_val,
        "declared_quantity": decl_qty_str,
        "unit_price": round(current_unit_price, 4),
        "historical_avg_unit_price": round(mean_price, 4),
        "historical_sample_count": len(historical_unit_prices),
        "signal": signal,
        "explanation": explanation,
        "disclaimer": "Internal analytical signal — not a legal finding.",
    }
