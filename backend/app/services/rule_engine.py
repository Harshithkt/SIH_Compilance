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

import yaml

from app.config import RULES_DIR
from app.services import quantity as qty


@dataclass
class Declaration:
    field: str
    value: str | None = None
    present: bool = False
    height_px: float | None = None
    bbox: dict | None = None


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
    for pack in list_rule_versions():
        if pack.version == version:
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
) -> Verdict:
    """Evaluate extracted declarations against a rule pack. Returns violations with
    clause citations and evidence bounding boxes, plus an explainable overall verdict.
    """
    violations: list[dict] = []
    not_assessed: list[dict] = []

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
        elif check_type == "numeric_ratio":
            # Best-effort sanity check only; never blocks a GO verdict on its own.
            passed = True
        else:
            passed = True

        if passed is None:
            not_assessed.append(
                {
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "title": rule["title"],
                    "reason": "Could not be measured from this capture — the declaration's position on the label was not established.",
                }
            )
            continue

        if not passed:
            violations.append(
                {
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "title": rule["title"],
                    "field": rule["field"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "bbox": decl.bbox if decl else None,
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
