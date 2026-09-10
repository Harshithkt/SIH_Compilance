"""Deterministic declaration extraction from OCR text boxes.

Regex/keyword layer first (per the memo: "regulation-mapped logic isn't prompt-dependent").
An LLM explainer can be layered on later for messy fields without changing this contract.
"""

from __future__ import annotations

import re

from app.services.ocr import TextBox
from app.services.rule_engine import Declaration

# field -> (label keywords incl. Hindi, value pattern used to refine the captured segment)
#
# Keyword precision matters: "Manufactured by" is the manufacturer declaration, while
# "Manufactured on" is the date declaration, so the date keywords require an explicit
# on/in/date token rather than matching the "manufactured" stem alone.
FIELD_PATTERNS: dict[str, tuple[list[str], str | None]] = {
    "mrp": (
        [
            r"\bm\.?\s?r\.?\s?p\b\.?",
            r"\bmaximum retail price\b",
            r"\bretail sale price\b",
            r"अधिकतम\s*खुदरा\s*मूल्य",
            r"मूल्य",
        ],
        r"(?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d{1,2})?",
    ),
    "net_quantity": (
        [
            r"\bnet\s*(?:qty|quantity|wt|weight)\b\.?",
            r"शुद्ध\s*(?:मात्रा|वजन)",
            r"मात्रा",
        ],
        r"\d+(?:\.\d+)?\s*(?:g|gm|gram|grams|kg|ml|l|litre|litres)\b",
    ),
    "mfg_date": (
        [
            r"\bmfg\.?\s*(?:date|dt)\b\.?",
            r"\bmfg\b\.?(?!\s*by)",
            r"\bmanufactured\s+(?:on|in)\b",
            r"\bdate of (?:manufacture|packing|import)\b",
            r"\bpacked on\b",
            r"निर्माण\s*(?:तिथि|दिनांक)",
        ],
        r"(?:0[1-9]|1[0-2])[\/\-\s](?:\d{4}|\d{2})\b",
    ),
    "manufacturer_details": (
        [
            r"\bmanufactured by\b",
            r"\bpacked by\b",
            r"\bmarketed by\b",
            r"\bimported by\b",
            r"\bmfd\.?\s*by\b",
            r"निर्माता",
            r"आयातक",
        ],
        None,
    ),
    "consumer_care": (
        [
            r"\bconsumer care\b",
            r"\bcustomer care\b",
            r"\bcomplaints?\b",
            r"\bhelpline\b",
            r"उपभोक्ता\s*सेवा",
        ],
        None,
    ),
    "country_of_origin": (
        [r"\bcountry of origin\b", r"\bmade in\b", r"उत्पत्ति\s*देश", r"मूल\s*देश"],
        None,
    ),
    "fssai_license_no": (
        [r"\bfssai\b", r"\blic\.?\s*no\b\.?", r"एफएसएसएआई"],
        r"\d{14}",
    ),
    "common_name": (
        [r"\bcommon name\b", r"\bgeneric name\b", r"\bproduct\s*name\b", r"सामान्य\s*नाम"],
        None,
    ),
    "best_before": (
        [
            r"\bbest before\b",
            r"\buse by\b",
            r"\bexpiry\s*(?:date)?\b",
            r"\bexp\.?\s*(?:date|dt)\b",
            r"सर्वोत्तम\s*उपयोग",
            r"समाप्ति\s*(?:तिथि|दिनांक)?",
        ],
        None,
    ),
}

ALL_FIELDS = list(FIELD_PATTERNS)
SEPARATORS = " :;-–—\t.|"


def _label_matches(line: str) -> list[tuple[int, int, str]]:
    """All declaration labels found in one line, as (start, end, field).

    Overlapping matches are resolved in favour of the longer (more specific) keyword,
    so "शुद्ध मात्रा" wins over "मात्रा" and "Manufactured by" is never read as a date.
    """
    matches: list[tuple[int, int, str]] = []
    for field, (keywords, _) in FIELD_PATTERNS.items():
        for keyword in keywords:
            for match in re.finditer(keyword, line, re.IGNORECASE):
                matches.append((match.start(), match.end(), field))

    matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, field in matches:
        if any(start < k_end and end > k_start for k_start, k_end, _ in kept):
            continue
        kept.append((start, end, field))
    return sorted(kept, key=lambda m: m[0])


def extract_declarations(boxes: list[TextBox]) -> dict[str, Declaration]:
    """Map recognised text lines onto LMPC declaration fields.

    A line is segmented at its declaration labels, so "Net Qty: 200 g  MRP: Rs 45" yields
    both fields, and each field's value is bounded by the next label rather than running
    to the end of the line. Every known field gets a Declaration whether or not it was
    found, so the rule engine can distinguish 'missing' from 'found but malformed' and the
    UI can mark fields 'verified on label' vs 'illegible'.
    """
    declarations: dict[str, Declaration] = {
        f: Declaration(field=f, present=False) for f in ALL_FIELDS
    }

    for box in boxes:
        line = box.text
        matches = _label_matches(line)

        for index, (_, end, field) in enumerate(matches):
            if declarations[field].present:
                continue

            segment_end = matches[index + 1][0] if index + 1 < len(matches) else len(line)
            segment = line[end:segment_end].strip(SEPARATORS).strip()

            value_pattern = FIELD_PATTERNS[field][1]
            if value_pattern:
                refined = re.search(value_pattern, segment, re.IGNORECASE)
                # Keep the raw segment when the pattern fails: a malformed declaration is
                # a rule-engine finding, not an extraction failure.
                value = refined.group(0).strip() if refined else segment
            else:
                value = segment

            if not value:
                continue

            declarations[field] = Declaration(
                field=field,
                value=value,
                present=True,
                height_px=box.height_px,
                bbox=box.bbox,
            )

    return declarations


def declaration_status(decl: Declaration) -> str:
    if not decl.present:
        return "missing"
    return "verified" if (decl.value or "").strip() else "illegible"


def resolve_entity_name(declarations: dict[str, Declaration]) -> str | None:
    """Entity resolution key: the manufacturer/packer/importer line, normalised.
    Used to aggregate scans into seller-level risk in the worklist.
    """
    decl = declarations.get("manufacturer_details")
    if not decl or not decl.value:
        return None
    name = re.split(r"[,\n]", decl.value)[0].strip()
    name = re.sub(r"\s+", " ", name)
    return name.title() if name else None
