"""Tests for Physical Verification calculation engine."""

from __future__ import annotations

import pytest

from app.services.physical_verification import evaluate_physical_measurement


class TestPhysicalVerification:

    def test_exact_quantity_pass(self):
        """Declared == Observed → PASS."""
        r = evaluate_physical_measurement("1 kg", "kg", 1000.0, "g")
        assert r["result"] == "PASS"

    def test_within_tolerance_pass(self):
        """Small shortfall within MPE → PASS."""
        # 1 kg declared, 990g observed, shortfall=10g, MPE for 1kg=15g → PASS
        r = evaluate_physical_measurement("1 kg", "kg", 990.0, "g")
        assert r["result"] == "PASS"
        assert r["shortfall"] == pytest.approx(10.0, abs=0.1)

    def test_beyond_tolerance_fail(self):
        """Shortfall exceeds MPE → FAIL."""
        # 1 kg declared, 960g observed, shortfall=40g, MPE=15g → FAIL
        r = evaluate_physical_measurement("1 kg", "kg", 960.0, "g")
        assert r["result"] == "FAIL"
        assert r["shortfall"] == pytest.approx(40.0, abs=0.1)

    def test_missing_declared_quantity_not_assessable(self):
        """Missing declared quantity → NOT_ASSESSABLE."""
        r = evaluate_physical_measurement(None, None, 960.0, "g")
        assert r["result"] == "NOT_ASSESSABLE"
        assert "declared" in r["explanation"].lower()

    def test_missing_observed_quantity_not_assessable(self):
        """Zero/negative observed → NOT_ASSESSABLE."""
        r = evaluate_physical_measurement("1 kg", "kg", 0.0, "g")
        assert r["result"] == "NOT_ASSESSABLE"

    def test_negative_observed_rejected(self):
        """Negative observed quantity → NOT_ASSESSABLE."""
        r = evaluate_physical_measurement("1 kg", "kg", -100.0, "g")
        assert r["result"] == "NOT_ASSESSABLE"

    def test_unsupported_unit_review(self):
        """Unrecognised unit → REVIEW."""
        r = evaluate_physical_measurement("1 kg", "kg", 900.0, "lbs")
        assert r["result"] == "REVIEW"

    def test_incompatible_dimension_review(self):
        """Mass declared vs volume observed → REVIEW."""
        r = evaluate_physical_measurement("1 kg", "kg", 900.0, "ml")
        assert r["result"] == "REVIEW"

    def test_kg_to_g_conversion(self):
        """kg declared compared with grams observed, correctly converts."""
        # 500g declared, 495g observed, shortfall=5g
        r = evaluate_physical_measurement("500 g", "g", 495.0, "g")
        assert r["result"] == "PASS"  # MPE for 500g = 15g absolute
        assert r["shortfall"] == pytest.approx(5.0, abs=0.1)

    def test_decimal_quantities(self):
        """Decimal declared and observed quantities work correctly."""
        r = evaluate_physical_measurement("0.5 kg", "kg", 490.0, "g")
        # 500g declared, 490g observed, shortfall=10g, MPE for 500g = 15g → PASS
        assert r["result"] == "PASS"

    def test_at_mpe_boundary_pass(self):
        """Exactly at MPE boundary → PASS."""
        # 1 kg declared, MPE = 15g, observed = 985g, shortfall = 15g → PASS (<=)
        r = evaluate_physical_measurement("1 kg", "kg", 985.0, "g")
        assert r["result"] == "PASS"

    def test_just_beyond_mpe_fail(self):
        """One gram beyond MPE → FAIL."""
        # 1 kg declared, MPE = 15g, observed = 984g, shortfall = 16g → FAIL
        r = evaluate_physical_measurement("1 kg", "kg", 984.0, "g")
        assert r["result"] == "FAIL"

    def test_calculation_details_present(self):
        """Result contains calculation_details for officer explanation."""
        r = evaluate_physical_measurement("1 kg", "kg", 960.0, "g")
        assert "details" in r
        assert "shortfall_base_units" in r["details"]
        assert "mpe_threshold_base_units" in r["details"]

    def test_enforcement_flag_present(self):
        """Enforcement flag is set appropriately."""
        r_fail = evaluate_physical_measurement("1 kg", "kg", 900.0, "g")
        assert r_fail["enforcement_flag"] != "NO_ACTION"

        r_pass = evaluate_physical_measurement("1 kg", "kg", 990.0, "g")
        assert r_pass["enforcement_flag"] == "NO_ACTION"

    def test_small_pack_50g(self):
        """Small 50g pack, 9% MPE applies."""
        r = evaluate_physical_measurement("50 g", "g", 46.0, "g")
        # MPE = 9% of 50g = 4.5g, shortfall = 4g → PASS
        assert r["result"] == "PASS"

    def test_small_pack_50g_fail(self):
        """Small 50g pack outside 9% MPE → FAIL."""
        r = evaluate_physical_measurement("50 g", "g", 40.0, "g")
        # shortfall = 10g > MPE 4.5g → FAIL
        assert r["result"] == "FAIL"

    def test_volume_ml_pass(self):
        """Volume test in ml → PASS."""
        r = evaluate_physical_measurement("500 ml", "ml", 495.0, "ml")
        assert r["result"] == "PASS"

    def test_volume_ml_fail(self):
        """Volume test in ml → FAIL."""
        r = evaluate_physical_measurement("500 ml", "ml", 480.0, "ml")
        assert r["result"] == "FAIL"
