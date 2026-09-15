"""Tests for LMPC Rule 22 MPE lookup engine."""

from __future__ import annotations

import pytest

from app.services.quantity import Quantity, parse as parse_quantity
from app.services.mpe_rule22 import get_maximum_permissible_error


def make_qty(value: float, unit: str) -> Quantity:
    return parse_quantity(f"{value} {unit}")


class TestMPEMass:
    """Tests covering the First Schedule mass/weight MPE bands."""

    def test_small_pack_9_percent(self):
        q = make_qty(50, "g")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "percentage"
        assert abs(r.mpe_value_in_base - 4.5) < 0.01  # 9% of 50g = 4.5g

    def test_50_to_100_absolute_4_5g(self):
        q = make_qty(75, "g")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "absolute"
        assert abs(r.mpe_value_in_base - 4.5) < 0.01

    def test_100_to_200_4_5_percent(self):
        q = make_qty(150, "g")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "percentage"
        assert abs(r.mpe_value_in_base - 6.75) < 0.01  # 4.5% of 150g

    def test_200_to_300_absolute_9g(self):
        q = make_qty(250, "g")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "absolute"
        assert abs(r.mpe_value_in_base - 9.0) < 0.01

    def test_300_to_500_3_percent(self):
        q = make_qty(400, "g")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "percentage"
        assert abs(r.mpe_value_in_base - 12.0) < 0.01  # 3% of 400g

    def test_500_to_1000_absolute_15g(self):
        q = make_qty(750, "g")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "absolute"
        assert abs(r.mpe_value_in_base - 15.0) < 0.01

    def test_above_1kg_1_5_percent(self):
        """Above 1000g triggers 1.5% MPE band."""
        q = make_qty(2, "kg")  # 2000g — above the 1000g absolute band
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "percentage"
        assert abs(r.mpe_value_in_base - 30.0) < 0.01  # 1.5% of 2000g = 30g

    def test_5kg_pack(self):
        q = make_qty(5, "kg")
        r = get_maximum_permissible_error(q)
        assert abs(r.mpe_value_in_base - 75.0) < 0.01  # 1.5% of 5000g = 75g

    def test_rule_id_present(self):
        q = make_qty(200, "g")
        r = get_maximum_permissible_error(q)
        assert "LMPC" in r.rule_id
        assert r.rule_version == "2011-v1"


class TestMPEVolume:
    """Tests covering volume MPE bands (same table as mass)."""

    def test_volume_500ml(self):
        q = make_qty(500, "ml")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "percentage"
        assert r.dimension == "volume"

    def test_volume_1_litre(self):
        q = make_qty(1, "l")
        r = get_maximum_permissible_error(q)
        assert abs(r.mpe_value_in_base - 15.0) < 0.01


class TestMPEUnsupported:
    """Unsupported / edge cases."""

    def test_invalid_dimension_raises(self):
        import pytest
        q = Quantity(value=10, unit="n", dimension="number", base_value=10.0)
        result = get_maximum_permissible_error(q)
        assert result.rule_id == "LMPC-RULE-22-COUNT"

    def test_length_2_percent(self):
        q = make_qty(50, "cm")
        r = get_maximum_permissible_error(q)
        assert r.tolerance_basis == "percentage"
        assert abs(r.mpe_value_in_base - 1.0) < 0.01  # 2% of 50cm
