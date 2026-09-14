"""Tests for Phase 2: Manufacturer / Packer / Importer role extraction.

Design contract being tested:
  1. Extraction layer -- extract_entity_declarations() classifies OCR evidence
     into EntityDeclaration objects.  extraction_status is an EXTRACTION SIGNAL.
  2. extraction_status == "found" does NOT imply legal compliance.
  3. Rule engine entity_role_presence check_type is the only layer that
     decides compliance.  Extraction and compliance are strictly separate.
"""
from __future__ import annotations

import pytest

from app.services.extraction import EntityDeclaration, extract_entity_declarations, _has_address_evidence
from app.services.ocr import ManualTextProvider
from app.services.rule_engine import Declaration, evaluate, get_rule_pack

_provider = ManualTextProvider()


def boxes_from(lines: list[str]):
    return _provider.extract_from_text("\n".join(lines))


def entity_decls_from(lines: list[str]) -> list[EntityDeclaration]:
    return extract_entity_declarations(boxes_from(lines))


# ---------------------------------------------------------------------------
# Address evidence heuristic (user adjustment #2)
# ---------------------------------------------------------------------------

class TestAddressEvidence:
    def test_pin_code_is_address_evidence(self):
        assert _has_address_evidence("Plot 22, Pune 411026") is True

    def test_address_keyword_road_is_evidence(self):
        assert _has_address_evidence("14 Dockyard Road, Mumbai") is True

    def test_address_keyword_nagar_is_evidence(self):
        assert _has_address_evidence("Shivaji Nagar, Delhi") is True

    def test_plain_company_name_is_not_address_evidence(self):
        assert _has_address_evidence("Sunrise Foods") is False

    def test_very_short_text_is_not_address_evidence(self):
        assert _has_address_evidence("AB") is False

    def test_empty_string_is_not_address_evidence(self):
        assert _has_address_evidence("") is False

    def test_digit_word_mixed_long_enough_is_evidence(self):
        assert _has_address_evidence("Plot 22A") is True
        assert _has_address_evidence("XX") is False  # no digit, no keyword, too short


# ---------------------------------------------------------------------------
# Role detection -- English patterns
# ---------------------------------------------------------------------------

class TestManufacturerRole:
    def test_manufactured_by_detected(self):
        eds = entity_decls_from(["Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026"])
        mfr = [e for e in eds if e.role == "manufacturer"]
        assert len(mfr) >= 1
        assert mfr[0].entity_name == "Sunrise Foods Pvt Ltd"
        assert mfr[0].extraction_status == "found"
        assert mfr[0].address_text is not None

    def test_manufacturer_keyword_detected(self):
        eds = entity_decls_from(["Manufacturer: Kamdhenu Dairy, Jaipur"])
        mfr = [e for e in eds if e.role == "manufacturer"]
        assert len(mfr) >= 1
        assert mfr[0].entity_name == "Kamdhenu Dairy"

    def test_mfg_by_alias_detected(self):
        eds = entity_decls_from(["Mfg. by: Green Valley Foods, Industrial Area, Nashik"])
        mfr = [e for e in eds if e.role == "manufacturer"]
        assert len(mfr) >= 1
        assert mfr[0].extraction_status == "found"


class TestPackerRole:
    def test_packed_by_detected(self):
        eds = entity_decls_from(["Packed by: Greenleaf Packagers"])
        pkr = [e for e in eds if e.role == "packer"]
        assert len(pkr) >= 1
        assert pkr[0].entity_name == "Greenleaf Packagers"
        assert pkr[0].extraction_status == "partial"
        assert pkr[0].address_text is None

    def test_packed_and_marketed_by_maps_to_packer_only(self):
        """Adjustment #1: 'packed and marketed by' must map to packer only."""
        eds = entity_decls_from(["Packed and marketed by: FreshPack Ltd, 32 MG Road, Bengaluru 560001"])
        roles = {e.role for e in eds}
        assert "packer" in roles
        assert "manufacturer" not in roles
        assert "importer" not in roles

    def test_packer_with_address_is_found(self):
        eds = entity_decls_from(["Packed by: Greenleaf Packagers, Sector 12, Noida 201301"])
        pkr = [e for e in eds if e.role == "packer"]
        assert len(pkr) >= 1
        assert pkr[0].extraction_status == "found"


class TestImporterRole:
    def test_imported_by_detected(self):
        eds = entity_decls_from(["Imported by: Global Trade Imports, 14 Dockyard Road, Mumbai"])
        imp = [e for e in eds if e.role == "importer"]
        assert len(imp) >= 1
        assert imp[0].entity_name == "Global Trade Imports"
        assert imp[0].extraction_status == "found"

    def test_imported_and_marketed_by_maps_to_importer_only(self):
        """Adjustment #1: 'imported and marketed by' -> importer role only."""
        eds = entity_decls_from(["Imported and marketed by: Best Imports Co., Andheri, Mumbai 400053"])
        roles = {e.role for e in eds}
        assert "importer" in roles
        assert "manufacturer" not in roles
        assert "packer" not in roles


# ---------------------------------------------------------------------------
# Hindi patterns
# ---------------------------------------------------------------------------

class TestHindiRoles:
    def test_hindi_manufacturer_detected(self):
        eds = entity_decls_from(["nirmaata: Kamdhenu Dairy Udyog, Jaipur 302029"])
        # ManualTextProvider is ASCII-safe; test with transliterated form
        # The Hindi keyword test uses the alias directly
        from app.services.ocr_normalize import find_entity_role_in_text
        hits = find_entity_role_in_text("निर्माता: कामधेनु डेयरी उद्योग, जयपुर 302029")
        assert any(h[2] == "manufacturer" for h in hits)


# ---------------------------------------------------------------------------
# Multi-role lines
# ---------------------------------------------------------------------------

class TestMultiRoleLines:
    def test_two_separate_lines_two_roles(self):
        eds = entity_decls_from([
            "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026",
            "Packed by: Greenleaf Packagers, Sector 12, Noida 201301",
        ])
        roles = {e.role for e in eds}
        assert "manufacturer" in roles
        assert "packer" in roles


# ---------------------------------------------------------------------------
# Evidence preservation (user adjustment #3)
# ---------------------------------------------------------------------------

class TestEvidencePreservation:
    def test_original_ocr_text_preserved(self):
        line = "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026"
        eds = entity_decls_from([line])
        mfr = [e for e in eds if e.role == "manufacturer"]
        assert len(mfr) >= 1
        assert mfr[0].original_ocr_text == line

    def test_raw_value_preserved(self):
        eds = entity_decls_from(["Imported by: Global Trade Imports, 14 Dockyard Road, Mumbai"])
        imp = [e for e in eds if e.role == "importer"]
        assert len(imp) >= 1
        assert imp[0].raw_value
        assert "Global Trade Imports" in imp[0].raw_value

    def test_extraction_status_found_does_not_bypass_rule_engine(self):
        """Three-tier architecture guard.

        extraction_status='found' must NOT bypass the rule engine.
        The existing R6-a-mfg-importer-packer presence rule on manufacturer_details
        still fires even when entity extraction reports 'found'.
        """
        eds = entity_decls_from(["Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026"])
        mfr = [e for e in eds if e.role == "manufacturer"]
        assert len(mfr) >= 1
        assert mfr[0].extraction_status == "found"

        pack = get_rule_pack("2022-v2")
        # manufacturer_details deliberately absent from declarations
        declarations: dict[str, Declaration] = {
            "net_quantity": Declaration(field="net_quantity", value="200 g", present=True,
                                        bbox={"x": 0.0, "y": 0.0, "w": 0.8, "h": 0.03}),
            "mrp": Declaration(field="mrp", value="Rs. 45.00", present=True,
                               bbox={"x": 0.0, "y": 0.0, "w": 0.8, "h": 0.03}),
            "mfg_date": Declaration(field="mfg_date", value="07/2026", present=True,
                                    bbox={"x": 0.0, "y": 0.0, "w": 0.8, "h": 0.03}),
        }
        verdict = evaluate(pack, declarations, {"is_food_item": False, "is_imported": False}, eds)
        assert verdict.result in ("FIX", "REVIEW")
        assert any(v["rule_id"] == "R6-a-mfg-importer-packer" for v in verdict.violations)


# ---------------------------------------------------------------------------
# Rule engine entity_role_presence check_type
# ---------------------------------------------------------------------------

class TestEntityRolePresenceCheck:
    def _eval_with_role_rule(
        self,
        eds: list[EntityDeclaration],
        *,
        role: str,
        require_address: bool,
    ) -> bool:
        from app.services.rule_engine import RulePack, evaluate

        raw_pack = {
            "version": "test-v0",
            "title": "Test pack",
            "effective_date": "2024-01-01",
            "rules": [
                {
                    "id": f"TEST-{role}",
                    "clause": "Test",
                    "title": f"Test {role} presence",
                    "field": role,
                    "check_type": "entity_role_presence",
                    "params": {"role": role, "require_address": require_address},
                    "severity": "high",
                    "message": f"Missing {role}",
                }
            ],
        }
        pack = RulePack(raw_pack, "test.yaml")
        verdict = evaluate(pack, {}, {}, eds)
        return len(verdict.violations) == 0

    def test_role_with_address_passes_require_address_true(self):
        eds = entity_decls_from(["Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026"])
        assert self._eval_with_role_rule(eds, role="manufacturer", require_address=True) is True

    def test_role_without_address_fails_require_address_true(self):
        eds = entity_decls_from(["Packed by: Greenleaf Packagers"])
        assert self._eval_with_role_rule(eds, role="packer", require_address=True) is False

    def test_role_without_address_passes_require_address_false(self):
        eds = entity_decls_from(["Packed by: Greenleaf Packagers"])
        assert self._eval_with_role_rule(eds, role="packer", require_address=False) is True

    def test_absent_role_fails_regardless_of_require_address(self):
        eds = entity_decls_from(["Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026"])
        assert self._eval_with_role_rule(eds, role="importer", require_address=False) is False
        assert self._eval_with_role_rule(eds, role="importer", require_address=True) is False

    def test_no_entity_decls_fails_gracefully(self):
        assert self._eval_with_role_rule([], role="manufacturer", require_address=False) is False
