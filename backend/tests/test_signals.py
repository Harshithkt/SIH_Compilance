"""Tests for P1/P2 signal features: contact validation, consistency, history signal, public dashboard."""

from __future__ import annotations

import pytest
from app.services.contact_validator import validate_contact_details, PHONE_PATTERN, EMAIL_PATTERN


class TestContactValidatorPatterns:
    """Unit tests for phone/email regex patterns — no DB needed."""

    def test_valid_indian_mobile(self):
        assert PHONE_PATTERN.match("9876543210")

    def test_valid_indian_mobile_with_91(self):
        assert PHONE_PATTERN.match("+919876543210")

    def test_valid_tollfree(self):
        assert PHONE_PATTERN.match("1800123456")

    def test_invalid_too_short(self):
        assert not PHONE_PATTERN.match("12345")

    def test_invalid_letters(self):
        assert not PHONE_PATTERN.match("abcdefghij")

    def test_valid_email(self):
        assert EMAIL_PATTERN.match("care@company.com")

    def test_valid_email_subdomains(self):
        assert EMAIL_PATTERN.match("support@mail.brand.in")

    def test_invalid_email_no_at(self):
        assert not EMAIL_PATTERN.match("carecompany.com")

    def test_invalid_email_no_domain(self):
        assert not EMAIL_PATTERN.match("care@")

    def test_invalid_email_no_tld(self):
        assert not EMAIL_PATTERN.match("care@company")


class TestMultiUnitConsistencyLogic:
    """Tests the consistency service logic without full DB scan."""

    def test_insufficient_evidence_single_unit(self):
        """Single unit = insufficient evidence."""
        from unittest.mock import MagicMock, patch
        from app.services.multi_unit_consistency import check_multi_unit_consistency

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [MagicMock()]  # 1 scan
        result = check_multi_unit_consistency(mock_db, "visit-001")
        assert result["status"] == "INSUFFICIENT_EVIDENCE"

    def test_no_units_returns_insufficient(self):
        """Zero units = insufficient evidence."""
        from unittest.mock import MagicMock
        from app.services.multi_unit_consistency import check_multi_unit_consistency

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = check_multi_unit_consistency(mock_db, "visit-002")
        assert result["status"] == "INSUFFICIENT_EVIDENCE"


class TestHistorySignalLogic:
    """Tests the history signal service without full DB scan."""

    def test_no_entity_no_adverse(self):
        """Missing entity → no prior adverse."""
        from unittest.mock import MagicMock
        from app.services.history_signal import get_historical_enforcement_signal

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = get_historical_enforcement_signal(mock_db, "unknown-entity")
        assert result["signal_level"] == "NO_PRIOR_ADVERSE"

    def test_disclaimer_always_present(self):
        """Disclaimer must always be present in result."""
        from unittest.mock import MagicMock
        from app.services.history_signal import get_historical_enforcement_signal

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = get_historical_enforcement_signal(mock_db, "ent-001")
        assert "not a legal determination" in result["disclaimer"].lower()

    def test_no_repeat_offender_wording(self):
        """Should never say 'repeat offender' in any output."""
        from unittest.mock import MagicMock
        from app.services.history_signal import get_historical_enforcement_signal

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = get_historical_enforcement_signal(mock_db, "ent-002")
        assert "repeat offender" not in result["display_message"].lower()


class TestPriceAnomalyLogic:
    """Tests the price anomaly service."""

    def test_insufficient_history_when_no_scans(self):
        """No historical data → INSUFFICIENT_HISTORY."""
        from unittest.mock import MagicMock, patch
        from app.services.price_anomaly import compute_price_anomaly_signal

        mock_scan = MagicMock()
        mock_scan.id = "scan-001"
        mock_scan.product_name = "Test Product"
        mock_scan.declarations = []

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scan
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = compute_price_anomaly_signal(mock_db, "scan-001")
        assert result["signal"] == "INSUFFICIENT_HISTORY"

    def test_disclaimer_is_not_legal_finding(self):
        """Disclaimer always says not a legal finding."""
        from unittest.mock import MagicMock
        from app.services.price_anomaly import compute_price_anomaly_signal

        mock_scan = MagicMock()
        mock_scan.id = "scan-001"
        mock_scan.declarations = []
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_scan
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = compute_price_anomaly_signal(mock_db, "scan-001")
        assert "not a legal finding" in result["disclaimer"].lower()


class TestPublicAggregatePrivacy:
    """Checks that public aggregate never exposes PII."""

    def test_aggregate_excludes_seller_identity(self):
        """Result must not include any seller names or officer names."""
        from unittest.mock import MagicMock
        from app.services.public_aggregate import get_public_aggregate_metrics

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []

        result = get_public_aggregate_metrics(mock_db)
        # Verify no sensitive fields in result keys
        sensitive_keys = {"seller_name", "entity_name", "officer_name", "case_notes", "evidence"}
        result_keys = set(result.keys())
        assert not result_keys.intersection(sensitive_keys)

    def test_aggregate_denominator_excludes_review(self):
        """REVIEW verdicts must not count as compliant."""
        from unittest.mock import MagicMock, patch
        from app.services.public_aggregate import get_public_aggregate_metrics

        mock_scan = MagicMock()
        mock_scan.verdict = "REVIEW"
        mock_scan.gps_lat = None
        mock_scan.is_food_item = False

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [mock_scan]

        result = get_public_aggregate_metrics(mock_db)
        # With 1 REVIEW scan, compliant=0, non_compliant=0, valid_evaluations=0
        # compliance_rate_percent should be 0 (not 100)
        assert result["compliant_count"] == 0
        assert result["compliance_rate_percent"] == 0.0

    def test_empty_dataset_handled(self):
        """Zero inspections returns zeros safely."""
        from unittest.mock import MagicMock
        from app.services.public_aggregate import get_public_aggregate_metrics

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []

        result = get_public_aggregate_metrics(mock_db)
        assert result["total_inspections"] == 0
        assert result["compliance_rate_percent"] == 0.0

    def test_disclaimer_present(self):
        """Disclaimer must always be in response."""
        from unittest.mock import MagicMock
        from app.services.public_aggregate import get_public_aggregate_metrics

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []
        result = get_public_aggregate_metrics(mock_db)
        assert "disclaimer" in result
