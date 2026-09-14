"""Append-only, hash-chained evidence ledger.

Each scan is committed as one ledger entry whose hash covers both the scan payload and
the previous entry's hash. Altering any earlier record (or the image it points at)
breaks every subsequent hash, which `verify_chain` detects and reports by sequence
number — this is the live demo the memo calls for: edit a stored photo, re-verify, watch
the chain break.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Scan

GENESIS_HASH = "0" * 64


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_payload(scan: Scan) -> dict:
    """The exact set of facts the chain commits to. Order is fixed and the JSON is
    canonicalised so the hash is reproducible by any third party verifying the docket.
    """
    return {
        "scan_id": scan.id,
        "officer_name": scan.officer_name,
        "image_sha256": scan.image_sha256,
        "captured_at": scan.captured_at.isoformat(),
        "gps": {"lat": scan.gps_lat, "lon": scan.gps_lon},
        "rule_version": scan.rule_version,
        "verdict": scan.verdict,
        "declarations": sorted(
            [
                {
                    "field": d.field,
                    "value": d.value,
                    "present": d.present,
                    "status": d.status,
                }
                for d in scan.declarations
            ],
            key=lambda d: d["field"],
        ),
        "not_assessed": sorted(
            [entry["rule_id"] for entry in (scan.not_assessed or [])]
        ),
        "violations": sorted(
            [
                {"rule_id": v.rule_id, "clause": v.clause, "severity": v.severity}
                for v in scan.violations
            ],
            key=lambda v: v["rule_id"],
        ),
        "entity_roles": sorted(
            [
                {
                    "role": er.role,
                    "entity_name": er.entity_name,
                    "address_text": er.address_text,
                    "extraction_status": er.extraction_status,
                }
                for er in (scan.entity_roles or [])
            ],
            key=lambda er: (er["role"], er["entity_name"] or ""),
        ),
    }


def payload_hash(payload: dict) -> str:
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def entry_hash(prev_hash: str, p_hash: str, sequence: int) -> str:
    return sha256_bytes(f"{prev_hash}{p_hash}{sequence}".encode("utf-8"))


def _last_entry(db: Session) -> LedgerEntry | None:
    return db.execute(
        select(LedgerEntry).order_by(LedgerEntry.sequence.desc()).limit(1)
    ).scalar_one_or_none()


def append_scan(db: Session, scan: Scan) -> LedgerEntry:
    """Commit the scan's current state as a new ledger entry.

    Called on first capture and again after any officer correction: the earlier entry
    stays in the chain, so the record's history is preserved rather than overwritten.
    """
    last = _last_entry(db)
    sequence = (last.sequence + 1) if last else 1
    prev_hash = last.entry_hash if last else GENESIS_HASH

    payload = canonical_payload(scan)
    p_hash = payload_hash(payload)
    e_hash = entry_hash(prev_hash, p_hash, sequence)

    entry = LedgerEntry(
        scan_id=scan.id,
        sequence=sequence,
        prev_hash=prev_hash,
        payload=payload,
        payload_hash=p_hash,
        entry_hash=e_hash,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    """Recompute the whole chain and reconcile it against the live records.

    Three things are checked, and the first failure names the entry it occurred at:
      1. Each entry is internally consistent and correctly linked to the one before it.
      2. Each scan's current state matches its most recent entry — so a record edited
         outside the ledger is caught, while a properly appended correction is not.
      3. Each evidence image still hashes to the value committed at capture.
    """
    entries = db.execute(select(LedgerEntry).order_by(LedgerEntry.sequence)).scalars().all()
    prev_hash = GENESIS_HASH

    def broken(sequence: int, detail: str) -> dict:
        return {
            "valid": False,
            "checked_entries": len(entries),
            "broken_at_sequence": sequence,
            "detail": detail,
        }

    for entry in entries:
        if entry.prev_hash != prev_hash:
            return broken(
                entry.sequence,
                f"Chain link broken at entry {entry.sequence}: it does not follow entry {entry.sequence - 1}.",
            )
        if payload_hash(entry.payload) != entry.payload_hash:
            return broken(
                entry.sequence,
                f"Entry {entry.sequence} has been altered: its stored record no longer matches its committed hash.",
            )
        if entry_hash(entry.prev_hash, entry.payload_hash, entry.sequence) != entry.entry_hash:
            return broken(entry.sequence, f"Entry hash mismatch at entry {entry.sequence}.")

        prev_hash = entry.entry_hash

    for scan in db.execute(select(Scan)).scalars().all():
        latest = scan.ledger_entry
        if latest is None:
            return broken(0, f"Scan {scan.id} exists outside the ledger — it was never committed.")

        if canonical_payload(scan) != latest.payload:
            return broken(
                latest.sequence,
                f"Record tampering detected: scan {scan.id} no longer matches ledger entry "
                f"{latest.sequence}, and no correction was appended to account for the change.",
            )

        image_path = Path(scan.image_path)
        if not image_path.exists():
            return broken(
                latest.sequence,
                f"Evidence image for scan {scan.id} is missing from disk: file {image_path} could not be found.",
            )
        if sha256_file(image_path) != scan.image_sha256:
            return broken(
                latest.sequence,
                f"Evidence image for scan {scan.id} has been modified since capture — "
                "file hash does not match the hash committed at inspection time.",
            )

    amendments = len(entries) - len({entry.scan_id for entry in entries})
    detail = f"All {len(entries)} ledger entries verified; chain is intact from genesis."
    if amendments:
        detail += f" {amendments} of them record officer corrections appended to earlier inspections."

    return {
        "valid": True,
        "checked_entries": len(entries),
        "broken_at_sequence": None,
        "detail": detail,
    }
