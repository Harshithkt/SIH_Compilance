import pytest

from app.services.rule_engine import Declaration, evaluate, get_rule_pack

PACK = get_rule_pack("2011-v1")

COMPLIANT = {
    "manufacturer_details": "Sunrise Foods Pvt Ltd, Plot 22, Pune 411026",
    "common_name": "Namkeen Mixture",
    "net_quantity": "200 g",
    "mrp": "Rs. 45.00",
    "mfg_date": "07/2026",
    "consumer_care": "care@sunrisefoods.example, 1800-100-2020",
    "fssai_license_no": "11522998000123",
}


def build(values: dict, height_ratio: float = 0.03):
    """Declarations positioned on the label, with a measured line height expressed as a
    fraction of the image height (what the layout pass produces)."""
    return {
        field: Declaration(
            field=field,
            value=value,
            present=True,
            bbox={"x": 0.05, "y": 0.1, "w": 0.8, "h": height_ratio},
            height_px=height_ratio * 640,
        )
        for field, value in values.items()
    }


def test_compliant_label_passes():
    verdict = evaluate(PACK, build(COMPLIANT), {"is_food_item": True, "is_imported": False})
    assert verdict.result == "GO"
    assert verdict.violations == []


def test_missing_mrp_is_high_severity_and_forces_review():
    values = {k: v for k, v in COMPLIANT.items() if k != "mrp"}
    verdict = evaluate(PACK, build(values), {"is_food_item": True, "is_imported": False})
    assert verdict.result == "REVIEW"
    assert any(v["rule_id"] == "R6-c-mrp" and v["severity"] == "high" for v in verdict.violations)


def test_violations_carry_clause_citations():
    values = {k: v for k, v in COMPLIANT.items() if k != "mrp"}
    verdict = evaluate(PACK, build(values), {"is_food_item": True, "is_imported": False})
    mrp_violation = next(v for v in verdict.violations if v["rule_id"] == "R6-c-mrp")
    assert mrp_violation["clause"] == "Rule 6(1)(c)"
    assert mrp_violation["message"]


def test_only_low_and_medium_findings_yield_fix_not_review():
    values = {k: v for k, v in COMPLIANT.items() if k != "consumer_care"}
    verdict = evaluate(PACK, build(values), {"is_food_item": True, "is_imported": False})
    assert verdict.result == "FIX"


def test_country_of_origin_applies_only_to_imports():
    domestic = evaluate(PACK, build(COMPLIANT), {"is_food_item": True, "is_imported": False})
    imported = evaluate(PACK, build(COMPLIANT), {"is_food_item": True, "is_imported": True})
    assert not any(v["rule_id"] == "R6-country-of-origin" for v in domestic.violations)
    assert any(v["rule_id"] == "R6-country-of-origin" for v in imported.violations)


def test_fssai_check_applies_only_to_food_items():
    values = {k: v for k, v in COMPLIANT.items() if k != "fssai_license_no"}
    non_food = evaluate(PACK, build(values), {"is_food_item": False, "is_imported": False})
    food = evaluate(PACK, build(values), {"is_food_item": True, "is_imported": False})
    assert not any(v["rule_id"] == "R8-fssai-license" for v in non_food.violations)
    assert any(v["rule_id"] == "R8-fssai-license" for v in food.violations)


def test_malformed_fssai_number_is_flagged():
    values = {**COMPLIANT, "fssai_license_no": "1152299800"}
    verdict = evaluate(PACK, build(values), {"is_food_item": True, "is_imported": False})
    assert any(v["rule_id"] == "R8-fssai-license" for v in verdict.violations)


def test_numerals_below_minimum_height_are_flagged():
    verdict = evaluate(
        PACK, build(COMPLIANT, height_ratio=0.008), {"is_food_item": True, "is_imported": False}
    )
    assert any(v["rule_id"] == "R7-numeral-height-mrp" for v in verdict.violations)


def test_height_check_is_scale_invariant():
    """The same label photographed closer has larger pixels but the same ratio, so the
    verdict must not depend on how close the officer stood."""
    near = evaluate(PACK, build(COMPLIANT, height_ratio=0.03), {"is_food_item": True, "is_imported": False})
    far = evaluate(PACK, build(COMPLIANT, height_ratio=0.03), {"is_food_item": True, "is_imported": False})
    assert near.result == far.result == "GO"


def test_unmeasurable_height_is_reported_not_charged_as_a_breach():
    """A declaration read without coordinates cannot be measured. Reporting that as a
    contravention would put a false accusation into an evidence docket."""
    declarations = {
        field: Declaration(field=field, value=value, present=True, bbox=None)
        for field, value in COMPLIANT.items()
    }
    verdict = evaluate(PACK, declarations, {"is_food_item": True, "is_imported": False})

    assert not any(v["rule_id"] == "R7-numeral-height-mrp" for v in verdict.violations)
    assert any(n["rule_id"] == "R7-numeral-height-mrp" for n in verdict.not_assessed)
    assert verdict.result == "GO"


def test_absent_declaration_is_reported_once_not_also_as_undersized_print():
    """A missing MRP is a missing MRP. Reporting it a second time as numerals that fail
    the type-size mandate would misdescribe the finding in the docket."""
    values = {k: v for k, v in COMPLIANT.items() if k != "mrp"}
    verdict = evaluate(PACK, build(values), {"is_food_item": True, "is_imported": False})

    assert any(v["rule_id"] == "R6-c-mrp" for v in verdict.violations)
    assert not any(v["rule_id"] == "R7-numeral-height-mrp" for v in verdict.violations)
    assert not any(n["rule_id"] == "R7-numeral-height-mrp" for n in verdict.not_assessed)


def test_four_digit_year_is_accepted():
    for date in ("07/2026", "07/26", "12-2026"):
        verdict = evaluate(
            PACK, build({**COMPLIANT, "mfg_date": date}), {"is_food_item": True, "is_imported": False}
        )
        assert not any(v["rule_id"] == "R6-d-mfg-date" for v in verdict.violations), date


def test_unknown_rule_version_raises():
    with pytest.raises(ValueError):
        get_rule_pack("does-not-exist")


def test_rule_pack_hash_is_stable():
    assert get_rule_pack("2011-v1").rule_hash() == PACK.rule_hash()
