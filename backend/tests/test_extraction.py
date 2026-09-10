from app.services.extraction import extract_declarations, resolve_entity_name
from app.services.ocr import ManualTextProvider

provider = ManualTextProvider()


def declarations_from(lines: list[str]):
    return extract_declarations(provider.extract_from_text("\n".join(lines)))


def test_manufactured_by_is_not_read_as_manufacture_date():
    decls = declarations_from(
        ["Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026", "Mfg Date: 07/2026"]
    )
    assert decls["manufacturer_details"].value.startswith("Sunrise Foods")
    assert decls["mfg_date"].value == "07/2026"


def test_two_declarations_on_one_line_are_segmented():
    decls = declarations_from(["Net Quantity: 200 g   MRP: Rs. 45.00"])
    assert decls["net_quantity"].value == "200 g"
    assert decls["mrp"].value == "Rs. 45.00"


def test_hindi_declarations_are_extracted():
    decls = declarations_from(
        [
            "निर्माता: Kamdhenu Dairy Udyog, Jaipur 302029",
            "शुद्ध मात्रा: 500 ml",
            "अधिकतम खुदरा मूल्य: Rs. 620.00",
            "निर्माण तिथि: 07/2026",
        ]
    )
    assert decls["manufacturer_details"].present
    assert decls["net_quantity"].value == "500 ml"
    assert decls["mrp"].value == "Rs. 620.00"
    assert decls["mfg_date"].value == "07/2026"


def test_malformed_value_is_captured_not_dropped():
    """A too-short FSSAI number must surface as a malformed declaration so the rule
    engine reports the right contravention, rather than as a missing one."""
    decls = declarations_from(["FSSAI Lic No: 1152299800"])
    assert decls["fssai_license_no"].present
    assert decls["fssai_license_no"].value == "1152299800"


def test_absent_field_is_marked_missing():
    decls = declarations_from(["Net Quantity: 200 g"])
    assert decls["mrp"].present is False
    assert decls["mrp"].value is None


def test_entity_name_is_first_clause_of_manufacturer_line():
    decls = declarations_from(["Imported by: Global Trade Imports, 14 Dockyard Road, Mumbai"])
    assert resolve_entity_name(decls) == "Global Trade Imports"
