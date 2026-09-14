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
from dataclasses import dataclass, field as dc_field
from typing import Any

from app.services.ocr import TextBox
from app.services.ocr_normalize import find_entity_role_in_text, find_field_in_text, normalise_text
from app.services.rule_engine import Declaration


# ---------------------------------------------------------------------------
# EntityDeclaration — structured per-role entity extraction result
# ---------------------------------------------------------------------------
#
# Design contract (Phase 2):
#
#   extraction_status is an EXTRACTION SIGNAL only — it records what the OCR
#   pipeline found and how confidently.  It is NEVER a legal compliance verdict.
#   The three values mean:
#
#   "found"   — a name token AND recognizable address evidence were detected.
#               "Recognizable address evidence" requires at least one of:
#               • a PIN/postal code (≥ 5 consecutive digits), OR
#               • a known address keyword (road, street, nagar, colony, dist,
#                 district, taluk, tehsil, block, sector, phase, plot, unit,
#                 industrial, area, estate, city, town, village, marg, chowk,
#                 lane, avenue, bazaar), OR
#               • a digit-and-word segment of ≥ 8 characters.
#               Even "found" status does NOT imply legal compliance.
#
#   "partial" — a name token was detected but the remainder does not contain
#               recognizable address evidence.  This is a normal outcome for
#               labels that omit the address or where OCR could not read it.
#
#   "empty"   — the role keyword was matched but no usable entity name followed.
#
# Evidence preservation (adjustment #3):
#   Every field below carries the underlying OCR evidence so the DB record is
#   self-contained: raw_value (the full OCR segment), original_ocr_text (the
#   un-normalised OCR line), bbox and height_px (spatial evidence), and both
#   confidence tracks.

@dataclass
class EntityDeclaration:
    """Structured result of extracting one entity-role declaration from OCR output."""

    role: str                        # "manufacturer" | "packer" | "importer"
    entity_name: str | None          # first comma/newline clause (the legal name)
    address_text: str | None         # remainder if recognizable address evidence found
    raw_value: str                   # full OCR segment after the role keyword (evidence)
    # Evidence preservation — all fields carry original provenance
    ocr_confidence: float | None     # length-weighted OCR engine confidence
    extraction_confidence: float | None  # 1.0=name+address, 0.5=name only, None=empty
    original_ocr_text: str           # un-normalised OCR line (before corrections)
    bbox: dict | None                # {x, y, w, h} relative 0–1 from OCR/layout pass
    height_px: float | None          # line height in pixels from layout pass
    # Extraction-layer signal — NOT a legal determination
    extraction_status: str           # "found" | "partial" | "empty"


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


def compute_declaration_evidence(
    declaration_text: str,
    boxes: list[TextBox],
    fallback_bbox: dict | None = None,
    fallback_height: float | None = None,
) -> tuple[float | None, dict | None, float | None]:
    """Compute length-weighted OCR confidence, union bbox, and height_px.

    Matches tokens appearing in declaration_text to build a precise union
    bounding box covering the declaration evidence region across tokens or lines.
    """
    search_text = (declaration_text or "").lower().strip()
    if not search_text:
        return None, fallback_bbox, fallback_height

    matched_confs: list[float] = []
    matched_lengths: list[int] = []
    matched_bboxes: list[dict] = []
    heights: list[float] = []

    for box in boxes:
        token = box.text.strip()
        if not token or len(token) < _MIN_TOKEN_LEN:
            continue
        if token.lower() in search_text:
            if box.confidence is not None and box.confidence >= _MIN_TOKEN_CONF:
                matched_confs.append(box.confidence)
                matched_lengths.append(len(token))
            if box.bbox and isinstance(box.bbox, dict):
                matched_bboxes.append(box.bbox)
            if box.height_px:
                heights.append(box.height_px)

    conf: float | None = None
    if matched_confs:
        total_len = sum(matched_lengths)
        if total_len > 0:
            conf = round(sum(c * l for c, l in zip(matched_confs, matched_lengths)) / total_len, 4)

    union_bbox: dict | None = fallback_bbox
    if matched_bboxes:
        min_x = min(b["x"] for b in matched_bboxes)
        min_y = min(b["y"] for b in matched_bboxes)
        max_x = max(b["x"] + b["w"] for b in matched_bboxes)
        max_y = max(b["y"] + b["h"] for b in matched_bboxes)
        if max_x > min_x and max_y > min_y:
            union_bbox = {
                "x": round(min_x, 4),
                "y": round(min_y, 4),
                "w": round(max_x - min_x, 4),
                "h": round(max_y - min_y, 4),
            }

    max_height = max(heights) if heights else fallback_height
    return conf, union_bbox, max_height


def calculate_declaration_confidence(
    declaration_text: str,
    boxes: list[TextBox],
    *,
    line_text: str | None = None,
) -> float | None:
    """Aggregate OCR confidence for a declaration via compute_declaration_evidence."""
    target = declaration_text if (declaration_text and declaration_text.strip()) else (line_text or "")
    conf, _, _ = compute_declaration_evidence(target, boxes)
    return conf


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

            # Calculate OCR confidence and evidence bounding box
            ocr_confidence, union_bbox, height_px = compute_declaration_evidence(
                value, boxes_list, fallback_bbox=box.bbox, fallback_height=box.height_px
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
                height_px=height_px,
                bbox=union_bbox,
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


# ---------------------------------------------------------------------------
# Address evidence detection — user adjustment #2
# ---------------------------------------------------------------------------
#
# A remainder segment is only classified as address_text / extraction_status
# "found" when it contains RECOGNIZABLE address evidence.  Plain company
# names or marketing slogans that happen to follow a role keyword must NOT be
# treated as addresses; that would produce false "found" signals and could
# ultimately mislead the compliance layer.
#
# Heuristics (any ONE is sufficient):
#   1. A PIN/postal code: ≥ 5 consecutive digits (covers Indian 6-digit PINs
#      and international codes).
#   2. A known address keyword from _ADDRESS_KEYWORDS (road, street, nagar, …).
#   3. A mixed digit-and-word segment of ≥ 8 characters (e.g. "Plot 22").
#      Requires at least one digit AND one alphabetic character.

_ADDRESS_KEYWORDS = re.compile(
    r"\b(?:"
    r"road|street|nagar|colony|dist(?:rict)?|taluk|tehsil|"
    r"block|sector|phase|plot|unit|industrial|area|estate|"
    r"city|town|village|marg|chowk|lane|avenue|bazaar|"
    r"mohalla|ward|gali|quarters|layout|enclave|extension|"
    r"complex|building|bldg|floor|pin|p\.?\s*o\.?|"
    # Hindi address indicators
    r"नगर|कॉलोनी|जिला|ग्राम|मार्ग|चौक|गली|लेन"
    r")\b",
    re.IGNORECASE,
)

_PIN_CODE = re.compile(r"\b\d{5,}\b")
_DIGIT_WORD_MIXED = re.compile(r"(?=.*\d)(?=.*[a-zA-Z]).{8,}")


def _has_address_evidence(text: str) -> bool:
    """Return True only when *text* contains recognizable address evidence.

    Deliberately conservative: a short company name or a punctuation fragment
    returns False.  This prevents misleadingly upgrading extraction_status to
    "found" when there is no actual address information present.
    """
    if not text or len(text.strip()) < 4:
        return False
    stripped = text.strip()
    return (
        bool(_PIN_CODE.search(stripped))
        or bool(_ADDRESS_KEYWORDS.search(stripped))
        or bool(_DIGIT_WORD_MIXED.search(stripped))
    )


# ---------------------------------------------------------------------------
# Per-role entity extraction
# ---------------------------------------------------------------------------


def extract_entity_declarations(
    boxes: list[TextBox] | Any,
) -> list[EntityDeclaration]:
    """Extract structured entity-role declarations from OCR text boxes.

    For each OCR line that contains a manufacturer, packer, or importer role
    keyword, this function produces one EntityDeclaration per detected role.
    A single line can produce multiple EntityDeclarations when the line
    explicitly names more than one role (e.g. "Manufactured and Packed by:").

    Evidence preservation contract (adjustment #3):
        Every EntityDeclaration carries the full provenance of the underlying
        OCR line: raw_value, original_ocr_text, bbox, height_px, and both
        confidence tracks.  The DB record is therefore self-contained and can
        be audited without re-running OCR.

    Extraction-status contract (adjustment #2):
        extraction_status is set to "found" ONLY when recognizable address
        evidence is present in the remainder segment.  Anything less → "partial"
        or "empty".  extraction_status is NEVER a legal compliance signal.

    The existing extract_declarations() / manufacturer_details field is NOT
    modified by this function.  Both extraction paths coexist.
    """
    if hasattr(boxes, "regions"):
        boxes_list: list[TextBox] = boxes.regions
    elif isinstance(boxes, list):
        boxes_list = boxes
    else:
        boxes_list = list(boxes)

    results: list[EntityDeclaration] = []

    for box in boxes_list:
        original_line = box.text          # un-normalised — kept as evidence
        corrected_line = normalise_text(original_line)

        role_matches = find_entity_role_in_text(corrected_line)
        if not role_matches:
            continue

        # For each role keyword found in this line, extract the segment that
        # follows it (up to the next role keyword or end of line).
        for idx, (kw_start, kw_end, role) in enumerate(role_matches):
            # Segment boundary: from end of keyword to start of next keyword
            # (from ANY role, not just the same role — labels sometimes chain
            # multiple role declarations on one line)
            next_kw_start = role_matches[idx + 1][0] if idx + 1 < len(role_matches) else len(corrected_line)
            raw_segment = corrected_line[kw_end:next_kw_start].strip(" :;-–—\t.|")

            if not raw_segment:
                results.append(EntityDeclaration(
                    role=role,
                    entity_name=None,
                    address_text=None,
                    raw_value="",
                    ocr_confidence=None,
                    extraction_confidence=None,
                    original_ocr_text=original_line,
                    bbox=box.bbox,
                    height_px=box.height_px,
                    extraction_status="empty",
                ))
                continue

            # Split: first comma-or-newline clause → entity name; rest → address
            parts = re.split(r"[,\n]", raw_segment, maxsplit=1)
            entity_name = parts[0].strip() if parts else None
            remainder = parts[1].strip() if len(parts) > 1 else ""

            # Normalise entity name
            if entity_name:
                entity_name = re.sub(r"\s+", " ", entity_name).strip()

            # Address classification (adjustment #2): require recognizable evidence
            if remainder and _has_address_evidence(remainder):
                address_text = remainder
                extraction_status = "found"
                extraction_confidence: float | None = 1.0
            elif entity_name:
                address_text = None
                extraction_status = "partial"
                extraction_confidence = 0.5
            else:
                address_text = None
                extraction_status = "empty"
                extraction_confidence = None

            # OCR confidence and evidence bounding box
            ocr_conf, union_bbox, height_px = compute_declaration_evidence(
                raw_segment, boxes_list, fallback_bbox=box.bbox, fallback_height=box.height_px
            )

            results.append(EntityDeclaration(
                role=role,
                entity_name=entity_name or None,
                address_text=address_text,
                raw_value=raw_segment,          # full segment — evidence
                ocr_confidence=ocr_conf,
                extraction_confidence=extraction_confidence,
                original_ocr_text=original_line,  # un-normalised line — evidence
                bbox=union_bbox,                 # spatial provenance
                height_px=height_px,
                extraction_status=extraction_status,
            ))

    return results


def resolve_entity_name(
    declarations: dict[str, Declaration],
    entity_decls: list[EntityDeclaration] | None = None,
) -> str | None:
    """Entity resolution key: manufacturer/packer/importer name, normalised.

    Prefers the structured extraction results (entity_decls) when available,
    trying manufacturer → packer → importer in that order of legal precedence.
    Falls back to the monolithic manufacturer_details field for backward compat
    with callers that do not yet pass entity_decls.
    """
    if entity_decls:
        for preferred_role in ("manufacturer", "packer", "importer"):
            for ed in entity_decls:
                if ed.role == preferred_role and ed.entity_name:
                    return re.sub(r"\s+", " ", ed.entity_name).strip().title() or None

    # Backward-compat fallback: monolithic manufacturer_details field
    decl = declarations.get("manufacturer_details")
    if not decl or not decl.value:
        return None
    name = re.split(r"[,\n]", decl.value)[0].strip()
    name = re.sub(r"\s+", " ", name)
    return name.title() if name else None
