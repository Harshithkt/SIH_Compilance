"""Versioned, clause-cited LMPC rule engine.

Rules are loaded from YAML packs in app/rules/<version>.yaml. Every scan records which
rule_version was applied at inspection time (see models.Scan.rule_version) so a case can
always be re-examined against the rules as they stood on the inspection date, even after
newer rule packs are added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from app.config import RULES_DIR
from app.services import quantity as qty

if TYPE_CHECKING:
    from app.services.extraction import EntityDeclaration


@dataclass
class Declaration:
    field: str
    value: str | None = None
    present: bool = False
    height_px: float | None = None
    bbox: dict | None = None
    # OCR confidence: what the OCR engine measured for the tokens that form this
    # declaration.  None means it could not be calculated (e.g. manual entry,
    # or no matching tokens found).  Do not report None as 0.0.
    ocr_confidence: float | None = None
    # Extraction confidence: how reliably the value pattern matched (1.0 = pattern
    # matched, 0.5 = raw segment used, None = free-text field with no pattern).
    extraction_confidence: float | None = None
    # Original OCR text before normalisation corrections, for evidence preservation.
    original_ocr_text: str | None = None


@dataclass
class Verdict:
    result: str  # GO | FIX | REVIEW
    violations: list[dict] = field(default_factory=list)
    # Checks that could not be performed on this capture (e.g. numeral height when the
    # text was recognised without coordinates). Reported, never counted as a breach.
    not_assessed: list[dict] = field(default_factory=list)
    # Provisions that do not apply to this package at all — Rule 26 exemptions and the
    # Rule 3 scope limits. Recorded so the docket shows why a rule was not applied.
    exempted: list[dict] = field(default_factory=list)
    scope_note: str | None = None


class RulePack:
    def __init__(self, raw: dict, filename: str):
        self.version: str = raw["version"]
        self.title: str = raw.get("title", "")
        self.effective_date: str = raw.get("effective_date", "")
        self.superseded_by: str | None = raw.get("superseded_by")
        self.filename = filename
        self.rules: list[dict] = raw["rules"]

    def rule_hash(self) -> str:
        import hashlib

        return hashlib.sha256(
            yaml.safe_dump(self.rules, sort_keys=True).encode("utf-8")
        ).hexdigest()


@lru_cache(maxsize=None)
def _load_pack(path: str) -> RulePack:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return RulePack(raw, Path(path).name)


def list_rule_versions() -> list[RulePack]:
    return [_load_pack(str(p)) for p in sorted(RULES_DIR.glob("*.yaml"))]


def get_rule_pack(version: str) -> RulePack:
    norm = version.replace("lmpc_", "").replace("_", "-")
    for pack in list_rule_versions():
        if pack.version in (version, norm):
            return pack
    raise ValueError(f"Unknown rule version: {version}")


SEVERITY_WEIGHT = {"low": 1, "medium": 3, "high": 7}


def _applies(rule: dict, context: dict) -> bool:
    cond = rule.get("applies_if")
    if not cond:
        return True
    return bool(context.get(cond["field"])) == bool(cond["equals"])


def _check_presence(decl: Declaration | None) -> bool:
    return bool(decl and decl.present and (decl.value or "").strip())


def _check_regex(decl: Declaration | None, params: dict) -> bool:
    if not decl or not decl.present or not (decl.value or "").strip():
        return False
    flags = re.IGNORECASE if "i" in params.get("flags", "") else 0
    return re.match(params["pattern"], decl.value.strip(), flags) is not None


def _check_min_height(decl: Declaration | None, params: dict) -> bool | None:
    """Type size as a fraction of the label height, not as absolute pixels.

    The Second Schedule ties minimum height to pack size, and a photograph's pixel scale
    depends on how close the officer stood — so an absolute pixel threshold would make
    the verdict depend on camera distance. The measured line height relative to the
    image is the scale-invariant equivalent.

    None means 'could not be measured' — distinct from 'too small'. A declaration read
    without coordinates cannot be measured, and an unmeasurable check must never be
    reported as a contravention.
    """
    if not decl or not decl.bbox or "h" not in decl.bbox:
        return None
    return decl.bbox["h"] >= params["min_height_ratio"]


def _check_min_height_table1(
    decl: Declaration | None, params: dict, net_quantity_decl: Declaration | None
) -> bool | None:
    """Table I of the Second Schedule bands the minimum numeral height by pack size —
    1mm up to 200 g/ml, 2mm from 200 to 500, 4mm above — not one flat figure for every
    pack. This check honours that shape without claiming a millimetre measurement it
    cannot make: `params['base_ratio_per_mm']` is a label-height ratio calibrated for a
    1mm requirement (see the rule's own `reference` note for how, and its stated
    uncertainty), and the actual threshold scales up with the band the declared net
    quantity falls into, using app.services.quantity's Table I bands. A quantity that
    cannot be parsed falls back to the smallest (1mm) band rather than skipping the
    check, since that is the more conservative reading.

    Still returns None — 'could not be measured', never charged as a contravention —
    exactly where `_check_min_height` does: no bbox means no measurement.
    """
    if not decl or not decl.bbox or "h" not in decl.bbox:
        return None

    quantity = qty.parse(net_quantity_decl.value if net_quantity_decl else None)
    required_mm = qty.minimum_numeral_height_mm(quantity) if quantity else None
    if required_mm is None:
        required_mm = 1.0

    threshold = params["base_ratio_per_mm"] * required_mm
    return decl.bbox["h"] >= threshold


def evaluate(
    rule_pack: RulePack,
    declarations: dict[str, Declaration],
    context: dict,
    entity_declarations: "list[EntityDeclaration] | None" = None,
) -> Verdict:
    """Evaluate extracted declarations against a rule pack. Returns violations with
    clause citations and evidence bounding boxes, plus an explainable overall verdict.
    """
    violations: list[dict] = []
    not_assessed: list[dict] = []
    _entity_decls: list["EntityDeclaration"] = entity_declarations or []

    for rule in rule_pack.rules:
        if not _applies(rule, context):
            continue

        decl = declarations.get(rule["field"])
        check_type = rule["check_type"]
        passed: bool | None

        if check_type == "presence":
            passed = _check_presence(decl)
        elif check_type == "regex":
            passed = _check_regex(decl, rule["params"])
        elif check_type == "min_height_ratio":
            # A declaration that is not on the pack at all is already caught by its own
            # presence or format rule; reporting it a second time as undersized print
            # would misdescribe the finding.
            if not decl or not decl.present:
                continue
            passed = _check_min_height(decl, rule["params"])
        elif check_type == "numeral_height_table1":
            if not decl or not decl.present:
                continue
            passed = _check_min_height_table1(decl, rule["params"], declarations.get("net_quantity"))
        elif check_type == "entity_role_presence":
            # Role-aware presence check for the Phase 2 entity-role extraction.
            #
            # params:
            #   role:             "manufacturer" | "packer" | "importer"
            #   require_address:  bool (optional, default False)
            #
            # Design contract — separation of layers:
            #   This check reads extraction_status as one evidence input.
            #   The rule itself decides what constitutes compliance — the
            #   extractor never does.  "found" vs "partial" is an extraction
            #   signal; passing/failing is a compliance determination made here.
            #
            # Backward compat: if entity_declarations was not supplied (None or
            # empty), the rule fails with passed=False, same as 'not present'.
            params_role = rule.get("params", {}).get("role", "")
            require_addr = rule.get("params", {}).get("require_address", False)
            role_hits = [e for e in _entity_decls if e.role == params_role]
            role_bbox: dict | None = None
            if not role_hits:
                passed = False
            else:
                # Pick the highest-confidence hit for this role
                best = max(
                    role_hits,
                    key=lambda e: (e.ocr_confidence or 0.0),
                )
                role_bbox = best.bbox
                if require_addr:
                    passed = best.extraction_status == "found"
                else:
                    passed = best.extraction_status in ("found", "partial")
        elif check_type == "numeric_ratio":
            # Best-effort sanity check only; never blocks a GO verdict on its own.
            passed = True
        else:
            passed = True

        if passed is None:
            # Font-size checks produce None when bbox is absent.  The reason
            # message explicitly states that physical millimetre measurement is
            # not possible without scale calibration, so this is reported as
            # NOT_ASSESSABLE rather than as a contravention.
            is_height_check = check_type in ("min_height_ratio", "numeral_height_table1")
            reason = (
                "Physical text height cannot be conclusively established from this "
                "image without scale calibration. Reported as NOT_ASSESSABLE — "
                "the declaration's position on the label was not measured."
                if is_height_check
                else "Could not be measured from this capture — the declaration's "
                     "position on the label was not established."
            )
            not_assessed.append(
                {
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "title": rule["title"],
                    "reason": reason,
                }
            )
            continue

        if not passed:
            violation_bbox = decl.bbox if decl else (role_bbox if check_type == "entity_role_presence" else None)
            violations.append(
                {
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "title": rule["title"],
                    "field": rule["field"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "bbox": violation_bbox,
                }
            )

    if not violations:
        result = "GO"
    elif any(v["severity"] == "high" for v in violations):
        result = "REVIEW"
    else:
        result = "FIX"

    return Verdict(result=result, violations=violations, not_assessed=not_assessed)


def diff_rule_versions(old_version: str, new_version: str) -> list[dict]:
    """Compare two rule packs clause-by-clause, e.g. to show 'Rule 7 amended 2025 —
    verdict may change' when re-running an old scan against today's rules.
    """
    old_pack = get_rule_pack(old_version)
    new_pack = get_rule_pack(new_version)
    old_by_id = {r["id"]: r for r in old_pack.rules}
    new_by_id = {r["id"]: r for r in new_pack.rules}

    diffs = []
    for rid in set(old_by_id) | set(new_by_id):
        old_r, new_r = old_by_id.get(rid), new_by_id.get(rid)
        if old_r is None:
            diffs.append({"rule_id": rid, "change": "added", "new": new_r})
        elif new_r is None:
            diffs.append({"rule_id": rid, "change": "removed", "old": old_r})
        elif old_r != new_r:
            diffs.append({"rule_id": rid, "change": "modified", "old": old_r, "new": new_r})
    return diffs
