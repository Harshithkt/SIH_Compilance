"""Deterministic declaration extraction from OCR text boxes.

Regex/keyword layer (per the memo: "regulation-mapped logic isn't prompt-dependent").
An LLM explainer can be layered on for messy fields without changing this contract.

Changes from original:
  • Integrates ocr_normalize for OCR character-error correction and alias expansion.
  • Uses line-level TextBox objects (Tesseract provider now groups words into lines).
  • calculate_declaration_confidence() aggregates per-token OCR confidences correctly
    (weighted mean by token length) rather than searching for the full multi-word value
    as a substring of a single token — which always returned 0.0.
  • Declaration carries ocr_confidence (measured from OCR engine) separately from
    extraction_confidence (how well the value pattern matched).
  • Original OCR text is preserved alongside the extracted/normalised value.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.ocr import TextBox
from app.services.ocr_normalize import find_field_in_text, normalise_text
from app.services.rule_engine import Declaration

# ---------------------------------------------------------------------------
# Field patterns — value extraction regexes
#
# Keywords are now managed by ocr_normalize.FIELD_ALIASES; only the value
# patterns live here.  FIELD_PATTERNS is kept for the rule engine's benefit.
# ---------------------------------------------------------------------------

FIELD_PATTERNS: dict[str, str | None] = {
    "mrp": r"(?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d{1,2})?",
    "net_quantity": r"\d+(?:\.\d+)?\s*(?:g|gm|gram|grams|kg|ml|l|litre|litres)\b",
    "mfg_date": r"(?:0[1-9]|1[0-2])[\/\-\s](?:\d{4}|\d{2})\b",
    "manufacturer_details": None,
    "consumer_care": None,
    "country_of_origin": None,
    "fssai_license_no": r"\d{14}",
    "common_name": None,
    "best_before": None,
}

ALL_FIELDS = list(FIELD_PATTERNS)
SEPARATORS = " :;-–—\t.|"

# Minimum token length to be considered a meaningful OCR evidence token
_MIN_TOKEN_LEN = 2
# Minimum Tesseract confidence to count a token in the aggregate
_MIN_TOKEN_CONF = 0.0  # include all (even low-confidence tokens contribute)


# ---------------------------------------------------------------------------
# Confidence calculation — Step 3 fix
# ---------------------------------------------------------------------------


def calculate_declaration_confidence(
    declaration_text: str,
    boxes: list[TextBox],
    *,
    line_text: str | None = None,
) -> float | None:
    """Aggregate OCR confidence for a declaration.

    Strategy: length-weighted mean of individual token confidences.

    Rationale:
      • Longer tokens provide more OCR evidence than short ones (a 10-char word
        is a stronger signal than a 1-char character).
      • Mean is more robust than min for multi-token declarations — one poor
        token (e.g., a noisy punctuation character) should not dominate.
      • Min confidence is available via the `min_confidence` field in the
        returned dict — useful for critical single-character fields like dates.

    The function searches for tokens that appear in the relevant line text
    rather than requiring the full multi-word declaration value to match a
    single token (the original bug).

    Returns None when no matching tokens are found rather than returning 0.0,
    which would be misleading.
    """
    search_text = (line_text or declaration_text).lower()
    if not search_text.strip():
        return None

    matched_confs: list[float] = []
    matched_lengths: list[int] = []

    for box in boxes:
        token = box.text.strip()
        if len(token) < _MIN_TOKEN_LEN:
            continue
        if token.lower() in search_text and box.confidence >= _MIN_TOKEN_CONF:
            matched_confs.append(box.confidence)
            matched_lengths.append(len(token))

    if not matched_confs:
        return None

    total_len = sum(matched_lengths)
    if total_len == 0:
        return None

    weighted_mean = sum(c * l for c, l in zip(matched_confs, matched_lengths)) / total_len
    return round(weighted_mean, 4)


# ---------------------------------------------------------------------------
# Label matching — wraps ocr_normalize
# ---------------------------------------------------------------------------


def _label_matches(line: str) -> list[tuple[int, int, str]]:
    """All declaration labels found in one line, as (start, end, field).

    Delegates to ocr_normalize.find_field_in_text which handles both the
    original extraction patterns and the expanded alias dictionary.
    Overlapping matches are resolved in favour of the longer keyword.
    """
    return find_field_in_text(line)


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------


def extract_declarations(boxes: list[TextBox] | Any) -> dict[str, Declaration]:
    """Map recognised text lines onto LMPC declaration fields.

    A line is segmented at its declaration labels, so:
        "Net Qty: 200 g  MRP: Rs 45"
    yields both net_quantity and mrp, each bounded by the next label.

    Every known field gets a Declaration whether found or not, so the rule
    engine can distinguish 'missing' from 'found but malformed'.

    Confidence on each Declaration:
      • confidence: length-weighted mean OCR confidence from matching tokens
                    (None when no confident tokens found)
      Note: confidence=None is stored as NULL in the DB and reported honestly
      to the UI, rather than 0.0 which would look like a genuine measurement.
    """
    if hasattr(boxes, "regions"):
        boxes_list: list[TextBox] = boxes.regions
    elif isinstance(boxes, list):
        boxes_list = boxes
    else:
        boxes_list = list(boxes)

    declarations: dict[str, Declaration] = {
        f: Declaration(field=f, present=False) for f in ALL_FIELDS
    }

    for box in boxes_list:
        original_line = box.text

        # Layer 1: conservative OCR character corrections
        corrected_line = normalise_text(original_line)

        # Find all declaration labels in the (possibly corrected) line
        matches = _label_matches(corrected_line)

        for index, (_, end, field) in enumerate(matches):
            if declarations[field].present:
                continue

            segment_end = matches[index + 1][0] if index + 1 < len(matches) else len(corrected_line)
            segment = corrected_line[end:segment_end].strip(SEPARATORS).strip()

            value_pattern = FIELD_PATTERNS.get(field)
            if value_pattern:
                refined = re.search(value_pattern, segment, re.IGNORECASE)
                # Keep the raw segment when the pattern fails: a malformed
                # declaration is a rule-engine finding, not an extraction failure.
                value = refined.group(0).strip() if refined else segment
            else:
                value = segment

            if not value:
                continue

            # Calculate OCR confidence for this declaration (Steps 2-3 fix)
            ocr_confidence = calculate_declaration_confidence(
                value, boxes_list, line_text=corrected_line
            )
            # Extraction confidence: 1.0 if value pattern matched, 0.5 if raw segment used
            extraction_confidence: float | None = (
                1.0 if (value_pattern and re.search(value_pattern, segment, re.IGNORECASE))
                else (0.5 if value_pattern else None)
            )

            declarations[field] = Declaration(
                field=field,
                value=value,
                present=True,
                height_px=box.height_px,
                bbox=box.bbox,
                # Attach both confidence types — stored on Declaration for evidence
                ocr_confidence=ocr_confidence,
                extraction_confidence=extraction_confidence,
                original_ocr_text=original_line,
            )

    return declarations


# ---------------------------------------------------------------------------
# Helpers used by pipeline and rule router
# ---------------------------------------------------------------------------


def declaration_status(decl: Declaration) -> str:
    if not decl.present:
        return "missing"
    return "verified" if (decl.value or "").strip() else "illegible"


def resolve_entity_name(declarations: dict[str, Declaration]) -> str | None:
    """Entity resolution key: manufacturer/packer/importer line, normalised."""
    decl = declarations.get("manufacturer_details")
    if not decl or not decl.value:
        return None
    name = re.split(r"[,\n]", decl.value)[0].strip()
    name = re.sub(r"\s+", " ", name)
    return name.title() if name else None
