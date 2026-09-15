"""Authoritative Legal Metrology (Packaged Commodities) Rules, Rule 22 / First Schedule MPE engine.

Maximum Permissible Error (MPE) on net quantity declared by weight, volume, length or count.

Legal Reference:
Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 22 & First Schedule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
from app.services.quantity import Quantity, parse as parse_quantity


@dataclass(frozen=True)
class MPELookupResult:
    rule_id: str
    rule_version: str
    mpe_value_in_base: float  # In grams/ml/cm/count
    display_mpe: str
    tolerance_basis: str  # "percentage" | "absolute"
    declared_base_value: float
    dimension: str


def get_maximum_permissible_error(quantity: Quantity) -> MPELookupResult:
    """Calculates the Maximum Permissible Error (MPE) under LMPC Rule 22 / First Schedule.

    Returns the permissible shortfall in base units (g for mass, ml for volume, cm for length, units for count).
    """
    base_val = quantity.base_value
    dim = quantity.dimension

    if dim in ("mass", "volume"):
        # First Schedule Table for Mass/Volume
        if base_val <= 50:
            mpe = base_val * 0.09
            display = "9%"
            basis = "percentage"
        elif base_val <= 100:
            mpe = 4.5
            display = "4.5 g/ml"
            basis = "absolute"
        elif base_val <= 200:
            mpe = base_val * 0.045
            display = "4.5%"
            basis = "percentage"
        elif base_val <= 300:
            mpe = 9.0
            display = "9 g/ml"
            basis = "absolute"
        elif base_val <= 500:
            mpe = base_val * 0.03
            display = "3%"
            basis = "percentage"
        elif base_val <= 1000:
            mpe = 15.0
            display = "15 g/ml"
            basis = "absolute"
        else:
            mpe = base_val * 0.015
            display = "1.5%"
            basis = "percentage"

        return MPELookupResult(
            rule_id="LMPC-RULE-22-FIRST-SCHEDULE",
            rule_version="2011-v1",
            mpe_value_in_base=mpe,
            display_mpe=display,
            tolerance_basis=basis,
            declared_base_value=base_val,
            dimension=dim,
        )

    elif dim == "length":
        # First Schedule for Length (2%)
        mpe = base_val * 0.02
        return MPELookupResult(
            rule_id="LMPC-RULE-22-LENGTH",
            rule_version="2011-v1",
            mpe_value_in_base=mpe,
            display_mpe="2%",
            tolerance_basis="percentage",
            declared_base_value=base_val,
            dimension=dim,
        )

    elif dim == "number":
        # First Schedule for Number/Count
        if base_val <= 50:
            mpe = 0.0
            display = "0 (exact count required)"
            basis = "absolute"
        else:
            mpe = max(1.0, base_val * 0.02)
            display = "2%"
            basis = "percentage"

        return MPELookupResult(
            rule_id="LMPC-RULE-22-COUNT",
            rule_version="2011-v1",
            mpe_value_in_base=mpe,
            display_mpe=display,
            tolerance_basis=basis,
            declared_base_value=base_val,
            dimension=dim,
        )

    raise ValueError(f"Unsupported quantity dimension: {dim}")
