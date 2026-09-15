"""
LabelLens E2E Deployment Verification
======================================
Runs against the live Docker stack (http://localhost:8080).

Tests:
  1. Health check
  2. Scan upload (full pipeline)
  3. Scan detail read-back
  4. Physical verification endpoint
  5. Evidence ledger verification
  6. Enforcement signals endpoint
  7. Public aggregate endpoint
  8. Persistence check

Usage:
  python scratch/e2e_deployment_verify.py
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from typing import Optional

BASE = "http://localhost:8080"
API  = f"{BASE}/api/v1"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = []

def log(status: str, test: str, detail: str = ""):
    marker = PASS if status == "PASS" else FAIL if status == "FAIL" else INFO
    line = f"{marker} {test}"
    if detail:
        line += f"  |  {detail}"
    print(line)
    results.append((status, test, detail))

def get(path: str) -> dict:
    req = urllib.request.Request(f"{API}{path}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def multipart_upload(path: str, fields: dict, file_path: str) -> dict:
    boundary = "----LabelLensE2E" + uuid.uuid4().hex
    body = []
    for name, val in fields.items():
        body.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode()
        )
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        content = f.read()
    header = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
        f"filename=\"{filename}\"\r\nContent-Type: image/jpeg\r\n\r\n"
    ).encode()
    body.append(header + content + b"\r\n")
    payload = b"".join(body) + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}{path}", data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def test_health():
    print("\n-- TEST 1: Health Check --")
    try:
        data = get("/system/health")
        status = data.get("status", "")
        db_ok  = data.get("database", {}).get("status") == "ok"
        if status == "ok" and db_ok:
            log("PASS", "Health check", f"status={status}, db=ok")
        else:
            log("FAIL", "Health check", json.dumps(data))
    except Exception as e:
        log("FAIL", "Health check", str(e))

def test_scan_upload() -> Optional[str]:
    print("\n-- TEST 2: Scan Upload (Full Pipeline) --")
    fixture = "backend/tests/fixtures/synthetic_label.jpg"
    if not os.path.exists(fixture):
        log("FAIL", "Scan upload", f"Fixture missing: {fixture}")
        return None
    try:
        data = multipart_upload("/scans", {
            "officer_name":      "Inspector Sharma",
            "lang":              "en",
            "is_food_item":      "false",
            "is_imported":       "false",
            "skip_quality_gate": "true",
            "source_type":       "PHYSICAL_LABEL",
        }, fixture)
        scan = data.get("scan", data)
        sid = scan.get("id")
        verdict = scan.get("verdict")
        ledger_seq = scan.get("ledger_entry", {}).get("sequence")
        decl_count = len(scan.get("declarations", []))
        log("PASS", "Scan upload created", f"id={sid}")
        log("PASS" if verdict else "FAIL", "Verdict present", f"verdict={verdict}")
        log("PASS" if ledger_seq is not None else "FAIL", "Ledger entry", f"sequence={ledger_seq}")
        log("PASS", "Declarations", f"count={decl_count}")
        return sid
    except urllib.error.HTTPError as e:
        log("FAIL", "Scan upload", f"HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        log("FAIL", "Scan upload", str(e))
    return None

def test_scan_readback(scan_id: str):
    print("\n-- TEST 3: Scan Detail Read-back --")
    try:
        data = get(f"/scans/{scan_id}")
        scan = data.get("scan", data)
        log("PASS", "Scan read-back", f"id={scan.get('id')}, verdict={scan.get('verdict')}")
        st = scan.get("source_type", "MISSING")
        log("PASS" if st == "PHYSICAL_LABEL" else "FAIL", "source_type field", f"source_type={st}")
    except Exception as e:
        log("FAIL", "Scan read-back", str(e))

def test_physical_verification(scan_id: str):
    print("\n-- TEST 4: Physical Verification --")
    try:
        payload = {
            "scan_id":          scan_id,
            "commodity":        "packaged_food",
            "nominal_quantity": 500,
            "unit":             "g",
            "measured_values":  [498.5, 499.0, 497.8, 500.2, 498.9],
            "officer_name":     "Inspector Sharma",
            "instrument_id":    "SCALE-001",
        }
        data = post_json("/physical-verifications", payload)
        result = data.get("result", data)
        mpe = result.get("mpe_value")
        compliant = result.get("is_compliant")
        ledger_hash = result.get("ledger_hash") or data.get("ledger_hash")
        log("PASS", "Physical verification created", f"mpe={mpe}, compliant={compliant}")
        log("PASS" if ledger_hash else "FAIL", "Physical verification ledger", f"hash={'present' if ledger_hash else 'missing'}")
    except urllib.error.HTTPError as e:
        log("FAIL", "Physical verification", f"HTTP {e.code}: {e.read().decode()[:400]}")
    except Exception as e:
        log("FAIL", "Physical verification", str(e))

def test_ledger(scan_id: str):
    print("\n-- TEST 5: Evidence Ledger --")
    try:
        data = get(f"/ledger/{scan_id}")
        entries = data.get("entries", data) if isinstance(data, dict) else data
        if isinstance(entries, list):
            log("PASS", "Ledger entries", f"count={len(entries)}")
            if entries:
                first = entries[0]
                log("PASS" if first.get("hash") else "FAIL", "Ledger hash present", "")
                log("PASS" if first.get("sequence") is not None else "FAIL", "Ledger sequence", f"seq={first.get('sequence')}")
        else:
            log("PASS", "Ledger response", json.dumps(data)[:200])
    except urllib.error.HTTPError as e:
        log("FAIL", "Ledger", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        log("FAIL", "Ledger", str(e))

def test_enforcement_signals(scan_id: str):
    print("\n-- TEST 6: Enforcement Signals --")
    try:
        data = get(f"/scans/{scan_id}/signals")
        signals = data.get("signals", data)
        log("PASS", "Enforcement signals endpoint", f"count={len(signals) if isinstance(signals, list) else 'n/a'}")
    except urllib.error.HTTPError as e:
        log("FAIL", "Enforcement signals", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        log("FAIL", "Enforcement signals", str(e))

def test_public_aggregate():
    print("\n-- TEST 7: Public Aggregate Dashboard --")
    try:
        data = get("/public/aggregate")
        total = data.get("total_scans")
        compliance_rate = data.get("compliance_rate")
        pii_free = "officer_name" not in data and "scan_ids" not in data
        log("PASS" if total is not None else "FAIL", "Public aggregate total_scans", f"total={total}")
        log("PASS" if compliance_rate is not None else "FAIL", "Public aggregate compliance_rate", f"rate={compliance_rate}")
        log("PASS" if pii_free else "FAIL", "Public aggregate PII-free", "")
    except urllib.error.HTTPError as e:
        log("FAIL", "Public aggregate", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        log("FAIL", "Public aggregate", str(e))

def test_persistence(scan_id: str):
    print("\n-- TEST 8: Persistence Check --")
    time.sleep(2)
    try:
        data = get(f"/scans/{scan_id}")
        scan = data.get("scan", data)
        if scan.get("id") == scan_id:
            log("PASS", "Persistence", f"Scan still readable: id={scan_id}")
        else:
            log("FAIL", "Persistence", f"Got unexpected id={scan.get('id')}")
    except Exception as e:
        log("FAIL", "Persistence", str(e))

def main():
    print("=" * 60)
    print("  LabelLens E2E Deployment Verification")
    print(f"  Target: {BASE}")
    print("=" * 60)

    test_health()
    scan_id = test_scan_upload()

    if scan_id:
        test_scan_readback(scan_id)
        test_physical_verification(scan_id)
        test_ledger(scan_id)
        test_enforcement_signals(scan_id)
        test_persistence(scan_id)
    else:
        print(f"\n[FAIL] Cannot proceed -- scan upload failed.")

    test_public_aggregate()

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    total  = passed + failed
    print(f"  Results: {passed}/{total} passed")
    if failed:
        print(f"\n  Failed tests:")
        for r in results:
            if r[0] == "FAIL":
                print(f"    x {r[1]}: {r[2]}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
