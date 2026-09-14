"""OCR text normalisation for Legal Metrology label inspection.

This module operates in two distinct layers:

Layer 1 — Conservative OCR character-error correction
    Applied ONLY when a token is already a strong candidate for a known
    declaration/header keyword.  Never applied globally.

    Common OCR substitutions corrected:
      l → I   in QUANTITY, PRICE, QUALITY, RETAIL, LICENCE, etc.
      I → l   (less common, left to context)
      0 → O   in COUNTRY, ORIGIN, OF, etc.
      5 → S   in SECURITY, etc.
      8 → B   in BEST, etc.

    The correction table is intentionally small — only mistakes actually seen
    in the target domain.  Broad replacement would introduce more errors than
    it fixes.

Layer 2 — Field header alias → canonical field mapping
    Maps every known surface form of a declaration header to a canonical
    field name.  The original OCR text is always preserved alongside the
    normalised interpretation.

Usage:
    from app.services.ocr_normalize import normalise_line, correct_ocr_errors

    corrected = correct_ocr_errors("NET QUANTlTY")   # → "NET QUANTITY"
    field, norm = normalise_line("M.R.P.: Rs 45")    # → ("mrp", "MRP: Rs 45")
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Layer 1 — OCR character-error correction
# ---------------------------------------------------------------------------

# Each entry is (pattern, replacement, description).
# Pattern must be anchored to a known keyword context (not a global substitution).
_CHAR_CORRECTIONS: list[tuple[re.Pattern, str, str]] = []


def _ctx(pattern: str, replacement: str, description: str) -> None:
    """Register a contextual correction pattern."""
    _CHAR_CORRECTIONS.append((re.compile(pattern, re.IGNORECASE), replacement, description))


# l / I confusion in header words
_ctx(r"\bNET\s+QUANTlTY\b", "NET QUANTITY", "l→I in QUANTITY")
_ctx(r"\bNET\s+QUALlTY\b", "NET QUALITY", "l→I in QUALITY")
_ctx(r"\bMAXlMUM\b", "MAXIMUM", "l→I in MAXIMUM")
_ctx(r"\bRETAlL\b", "RETAIL", "l→I in RETAIL")
_ctx(r"\bRETAlL\s+PRlCE\b", "RETAIL PRICE", "l→I in RETAIL PRICE")
_ctx(r"\bMAXlMUM\s+RETAlL\s+PRlCE\b", "MAXIMUM RETAIL PRICE", "l→I in MRP full")
_ctx(r"\bMAXlMUM\s+RETAIL\s+PRlCE\b", "MAXIMUM RETAIL PRICE", "l→I mixed MRP")
_ctx(r"\bMAXIMUM\s+RETAlL\s+PRlCE\b", "MAXIMUM RETAIL PRICE", "l→I mixed MRP 2")
_ctx(r"\bPRlCE\b", "PRICE", "l→I in PRICE")
_ctx(r"\bLlCENCE\b", "LICENCE", "l→I in LICENCE")
_ctx(r"\bLlCENSE\b", "LICENSE", "l→I in LICENSE")
_ctx(r"\bNlRMATRl\b", "NIRMATRA", "l→I in Hindi transliteration")

# 0 / O confusion in header words
_ctx(r"\bC0UNTRY\b", "COUNTRY", "0→O in COUNTRY")
_ctx(r"\bC0UNTRY\s+0F\s+0RlGIN\b", "COUNTRY OF ORIGIN", "0→O full phrase")
_ctx(r"\b0RIGIN\b", "ORIGIN", "0→O in ORIGIN")
_ctx(r"\bC0NTENTS\b", "CONTENTS", "0→O in CONTENTS")
_ctx(r"\bC0NSUMER\b", "CONSUMER", "0→O in CONSUMER")

# 5 / S confusion
_ctx(r"\b5ECURITY\b", "SECURITY", "5→S in SECURITY")
_ctx(r"\bF55AI\b", "FSSAI", "5→S in FSSAI")
_ctx(r"\bF5SAI\b", "FSSAI", "5→S in FSSAI alt")
_ctx(r"\bFS5AI\b", "FSSAI", "5→S in FSSAI alt2")

# 8 / B confusion
_ctx(r"\b8EST\s+8EF0RE\b", "BEST BEFORE", "8→B in BEST BEFORE")
_ctx(r"\b8EST\s+BEFORE\b", "BEST BEFORE", "8→B in BEST")
_ctx(r"\bBEST\s+8EFORE\b", "BEST BEFORE", "8→B in BEFORE")


def correct_ocr_errors(text: str) -> str:
    """Apply conservative contextual OCR character corrections.

    Only corrects tokens that strongly match a known declaration keyword context.
    The original text is never modified outside of those contexts.
    """
    result = text
    for pattern, replacement, _desc in _CHAR_CORRECTIONS:
        result = pattern.sub(replacement, result)
    return result


# ---------------------------------------------------------------------------
# Layer 2 — Field header alias dictionary
# ---------------------------------------------------------------------------

# Each entry: canonical_field → list of alias patterns (regex, case-insensitive).
# Patterns are tried in order; first match wins.
# Original OCR text is always preserved alongside the canonical interpretation.

FIELD_ALIASES: dict[str, list[str]] = {
    "mrp": [
        r"\bm\.?\s?r\.?\s?p\.?\b",
        r"\bmaximum\s+retail\s+price\b",
        r"\bmax\.?\s+retail\s+price\b",
        r"\bretail\s+sale\s+price\b",
        r"\bretail\s+price\b",
        r"\brsale\s+price\b",
        r"अधिकतम\s*खुदरा\s*मूल्य",
        r"\bमूल्य\b",
    ],
    "net_quantity": [
        r"\bnet\s+(?:qty|quantity)\b\.?",
        r"\bnet\s+(?:wt|weight)\.?\b",
        r"\bcontents\b",
        r"\bnet\s+vol(?:ume)?\b",
        r"शुद्ध\s*(?:मात्रा|वजन|भार)",
        r"\bमात्रा\b",
    ],
    "mfg_date": [
        r"\bmfg\.?\s*(?:date|dt)\.?\b",
        r"\bmfg\.?\b(?!\s*by)",
        r"\bmanufactured\s+(?:on|in)\b",
        r"\bdate\s+of\s+(?:manufacture|packing|mfg|import)\b",
        r"\bpacked\s+on\b",
        r"निर्माण\s*(?:तिथि|तारीख|दिनांक)",
        r"पैकिंग\s*(?:तिथि|तारीख|दिनांक)",
    ],
    "manufacturer_details": [
        r"\bmanufactured\s+by\b",
        r"\bmanufacturer\b",
        r"\bmfg\.?\s*by\b",
        r"\bmfd\.?\s*by\b",
        r"\bpacked\s+(?:and\s+|&\s+)?marketed\s+by\b",
        r"\bpacked\s+by\b",
        r"\bmarketed\s+by\b",
        r"\bimported\s+by\b",
        r"\bimporter\b",
        r"निर्माता",
        r"निर्मित\s*द्वारा",
        r"आयातक",
        r"पैकर",
    ],
    "consumer_care": [
        r"\bconsumer\s+care\b",
        r"\bcustomer\s+care\b",
        r"\bcomplaints?\b",
        r"\bhelpline\b",
        r"\bcustomer\s+service\b",
        r"उपभोक्ता\s*(?:सेवा|शिकायत)",
        r"ग्राहक\s*सेवा",
    ],
    "country_of_origin": [
        r"\bcountry\s+of\s+origin\b",
        r"\bmade\s+in\b",
        r"\bproduct\s+of\b",
        r"उत्पत्ति\s*देश",
        r"मूल\s*देश",
    ],
    "fssai_license_no": [
        r"\bfssai\b",
        r"\blic(?:ence|ense)?\s*no\.?\b",
        r"\bfsn\s*no\.?\b",
        r"एफएसएसएआई",
    ],
    "common_name": [
        r"\bcommon\s+name\b",
        r"\bgeneric\s+name\b",
        r"\bproduct\s+name\b",
        r"सामान्य\s*नाम",
    ],
    "best_before": [
        r"\bbest\s+before\b",
        r"\bbest-before\b",
        r"\bbb\.?\s*(?:date)?\b",
        r"\buse\s+by\b",
        r"\bexpiry\s+date\b",
        r"\bexp(?:iry)?\s*(?:date|dt)?\b",
        r"\bbbd\b",
        r"सर्वोत्तम\s*उपयोग",
        r"समाप्ति\s*(?:तिथि|दिनांक)?",
    ],
}

# Compiled alias patterns (lazy-compiled on first use)
_COMPILED: dict[str, list[re.Pattern]] | None = None


def _get_compiled() -> dict[str, list[re.Pattern]]:
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = {
            field: [re.compile(pat, re.IGNORECASE) for pat in patterns]
            for field, patterns in FIELD_ALIASES.items()
        }
    return _COMPILED


def find_field_in_text(text: str) -> list[tuple[int, int, str]]:
    """Return all (start, end, canonical_field) tuples found in *text*.

    Overlapping matches are deduplicated in favour of the longer (more
    specific) keyword, consistent with extraction.py's _label_matches().
    """
    compiled = _get_compiled()
    raw: list[tuple[int, int, str]] = []
    for field, patterns in compiled.items():
        for pattern in patterns:
            for m in pattern.finditer(text):
                raw.append((m.start(), m.end(), field))

    # Sort: by start position, then by length descending (longer wins)
    raw.sort(key=lambda t: (t[0], -(t[1] - t[0])))

    # Remove overlaps — keep the first (longest) match at each position
    kept: list[tuple[int, int, str]] = []
    for start, end, fld in raw:
        if any(start < k_end and end > k_start for k_start, k_end, _ in kept):
            continue
        kept.append((start, end, fld))
    return sorted(kept, key=lambda t: t[0])


# ---------------------------------------------------------------------------
# Entity-role alias dictionary (manufacturer / packer / importer)
# ---------------------------------------------------------------------------
#
# Design contract (user adjustment #1):
#   • Every pattern maps to EXACTLY the role the text explicitly states.
#   • Combined phrases like "packed and marketed by" map to "packer" only —
#     marketing is not a regulated LMPC declaration role; inferring it would
#     create a false legal claim.
#   • No pattern is shared between roles; overlapping surface forms (e.g.
#     "manufactured and packed by") are listed explicitly under EACH role they
#     genuinely cover so there is no ambiguity about what the text asserts.
#   • Patterns are ordered from most-specific (longest) to least-specific so
#     the longest-match resolution in find_entity_role_in_text() de-duplicates
#     correctly.
#
# This dict is SEPARATE from FIELD_ALIASES intentionally: entity-role patterns
# require a different resolution strategy (one text span → one or more roles)
# compared to field-label patterns (one text span → exactly one field).

ENTITY_ROLE_ALIASES: dict[str, list[str]] = {
    "manufacturer": [
        # Combined phrases — manufacturer role only
        r"\bmanufactured\s+(?:and\s+)?packed\s+by\b",
        r"\bmanufactured\s+&\s+packed\s+by\b",
        r"\bmanufacturing\s+and\s+packing\s+by\b",
        # Simple manufacturer patterns
        r"\bmanufactured\s+by\b",
        r"\bmanufacturer\b",
        r"\bmfg\.?\s*by\b",
        r"\bmfd\.?\s*by\b",
        r"\bmanufacturing\s+unit\b",
        # Hindi
        r"निर्माता",
        r"निर्मित\s*द्वारा",
    ],
    "packer": [
        # Combined phrases — packer role only (marketing/distribution is NOT
        # a regulated declaration role under LMPC; map only the packing role)
        r"\bpacked\s+(?:and\s+|&\s+)?marketed\s+by\b",
        r"\bpacked\s+(?:and\s+|&\s+)?distributed\s+by\b",
        r"\bpacked\s+(?:and\s+|&\s+)?sold\s+by\b",
        # Simple packer patterns
        r"\bpacked\s+by\b",
        r"\bpacker\b",
        r"\bpackaging\s+by\b",
        # Hindi
        r"पैकर",
        r"पैक\s*किया\s*(?:गया\s+)?द्वारा",
        r"पैकिंग\s*(?:द्वारा|कर्ता)",
    ],
    "importer": [
        r"\bimported\s+(?:and\s+|&\s+)?marketed\s+by\b",
        r"\bimported\s+(?:and\s+|&\s+)?distributed\s+by\b",
        r"\bimported\s+by\b",
        r"\bimporter\b",
        r"\bsole\s+importer\b",
        r"\bauthorised\s+importer\b",
        r"\bauthorized\s+importer\b",
        # Hindi
        r"आयातक",
        r"आयात\s*किया\s*(?:गया\s+)?द्वारा",
    ],
}

# Compiled role-alias patterns (lazy-compiled on first use, separate cache
# from _COMPILED so entity-role and field lookups never interfere)
_ROLE_COMPILED: dict[str, list[re.Pattern]] | None = None


def _get_role_compiled() -> dict[str, list[re.Pattern]]:
    global _ROLE_COMPILED
    if _ROLE_COMPILED is None:
        _ROLE_COMPILED = {
            role: [re.compile(pat, re.IGNORECASE) for pat in patterns]
            for role, patterns in ENTITY_ROLE_ALIASES.items()
        }
    return _ROLE_COMPILED


def find_entity_role_in_text(text: str) -> list[tuple[int, int, str]]:
    """Return all (start, end, role) tuples found in *text*.

    Each tuple identifies a span that explicitly names an entity role
    (manufacturer, packer, or importer).  A single text span can match
    multiple roles only when the same span is covered by patterns from
    different role buckets (e.g. "manufactured and packed by" will produce
    both a manufacturer hit and a packer hit at the same position if such
    a combined pattern is registered under both roles).

    The same overlap-resolution logic as find_field_in_text() is applied
    WITHIN each role (longer match wins), but spans from DIFFERENT roles at
    the same position are all kept, since one text phrase can legitimately
    name two regulated roles simultaneously.
    """
    compiled = _get_role_compiled()
    # Collect all raw matches
    raw: list[tuple[int, int, str]] = []
    for role, patterns in compiled.items():
        role_hits: list[tuple[int, int, str]] = []
        for pattern in patterns:
            for m in pattern.finditer(text):
                role_hits.append((m.start(), m.end(), role))
        # Within each role: sort by position then by length desc (longest wins)
        role_hits.sort(key=lambda t: (t[0], -(t[1] - t[0])))
        # De-duplicate overlaps within the same role
        kept_for_role: list[tuple[int, int, str]] = []
        for start, end, role_name in role_hits:
            if any(
                start < k_end and end > k_start
                for k_start, k_end, _ in kept_for_role
            ):
                continue
            kept_for_role.append((start, end, role_name))
        raw.extend(kept_for_role)

    # Sort final list by position for deterministic caller iteration
    return sorted(raw, key=lambda t: t[0])


# ---------------------------------------------------------------------------
# Public normalisation entry point
# ---------------------------------------------------------------------------


def normalise_text(text: str) -> str:
    """Apply Layer 1 corrections to *text*, return corrected string.

    The caller is responsible for preserving the original for evidence.
    """
    return correct_ocr_errors(text)
