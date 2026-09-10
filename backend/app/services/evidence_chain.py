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
    last = _last_entry(db)
    sequence = (last.sequence + 1) if last else 1
    prev_hash = last.entry_hash if last else GENESIS_HASH

    p_hash = payload_hash(canonical_payload(scan))
    e_hash = entry_hash(prev_hash, p_hash, sequence)

    entry = LedgerEntry(
        scan_id=scan.id,
        sequence=sequence,
        prev_hash=prev_hash,
        payload_hash=p_hash,
        entry_hash=e_hash,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    """Recompute the whole chain. Reports the first sequence where the recorded hash
    diverges — whether because a scan record was edited, or the stored image no longer
    matches the hash committed at inspection time.
    """
    entries = db.execute(select(LedgerEntry).order_by(LedgerEntry.sequence)).scalars().all()
    prev_hash = GENESIS_HASH

    for entry in entries:
        scan = entry.scan
        expected_payload = payload_hash(canonical_payload(scan))

        if entry.prev_hash != prev_hash:
            return {
                "valid": False,
                "checked_entries": len(entries),
                "broken_at_sequence": entry.sequence,
                "detail": f"Chain link broken at entry {entry.sequence}: prev_hash does not match entry {entry.sequence - 1}.",
            }
        if expected_payload != entry.payload_hash:
            return {
                "valid": False,
                "checked_entries": len(entries),
                "broken_at_sequence": entry.sequence,
                "detail": f"Record tampering detected at entry {entry.sequence}: scan {scan.id} no longer hashes to its committed payload.",
            }
        if entry_hash(entry.prev_hash, entry.payload_hash, entry.sequence) != entry.entry_hash:
            return {
                "valid": False,
                "checked_entries": len(entries),
                "broken_at_sequence": entry.sequence,
                "detail": f"Entry hash mismatch at entry {entry.sequence}.",
            }

        image_path = Path(scan.image_path)
        if image_path.exists() and sha256_file(image_path) != scan.image_sha256:
            return {
                "valid": False,
                "checked_entries": len(entries),
                "broken_at_sequence": entry.sequence,
                "detail": f"Evidence image for scan {scan.id} has been modified since capture — file hash does not match the hash committed at inspection time.",
            }

        prev_hash = entry.entry_hash

    return {
        "valid": True,
        "checked_entries": len(entries),
        "broken_at_sequence": None,
        "detail": f"All {len(entries)} ledger entries verified; chain is intact from genesis.",
    }
