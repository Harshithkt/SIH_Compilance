/**
 * PhysicalVerification — P0 field weight/volume measurement panel.
 *
 * Provides a form for the officer to enter an observed physical measurement
 * and see whether it falls within LMPC Rule 22 MPE tolerance vs the declared
 * label quantity. The system calculates the shortfall; the officer confirms.
 *
 * Result is committed as a tamper-evident evidence record.
 */

import { useState } from "react";
import type { PhysicalVerification, PhysicalVerificationResult } from "../types";
import { api } from "../api";

interface Props {
  scanId: string;
  declaredQuantity?: string | null;
  declaredUnit?: string | null;
  onCommitted?: (pv: PhysicalVerification) => void;
}

const RESULT_STYLES: Record<PhysicalVerificationResult, { cls: string; label: string }> = {
  PASS: { cls: "badge-go", label: "PASS — Within Tolerance" },
  FAIL: { cls: "badge-fail", label: "FAIL — Exceeds MPE" },
  REVIEW: { cls: "badge-review", label: "REVIEW — Officer Attention Required" },
  NOT_ASSESSABLE: { cls: "badge-na", label: "NOT ASSESSABLE" },
};

const COMMON_UNITS = ["g", "kg", "ml", "l", "cm", "m"];

export default function PhysicalVerificationPanel({
  scanId,
  declaredQuantity,
  declaredUnit,
  onCommitted,
}: Props) {
  const [declaredQty, setDeclaredQty] = useState(declaredQuantity ?? "");
  const [declaredUt, setDeclaredUt] = useState(declaredUnit ?? "g");
  const [observedQty, setObservedQty] = useState("");
  const [observedUt, setObservedUt] = useState(declaredUnit ?? "g");
  const [sampleNo, setSampleNo] = useState(1);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PhysicalVerification | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const obs = parseFloat(observedQty);
    if (!obs || obs <= 0) {
      setError("Observed quantity must be a positive number.");
      return;
    }
    if (!declaredQty.trim()) {
      setError("Declared quantity is required.");
      return;
    }
    setLoading(true);
    try {
      const pv = await api.createPhysicalVerification({
        scan_id: scanId,
        declared_quantity: declaredQty,
        declared_unit: declaredUt,
        observed_quantity: obs,
        observed_unit: observedUt,
        sample_number: sampleNo,
        notes: notes.trim() || undefined,
      });
      setResult(pv);
      onCommitted?.(pv);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed. Please retry.");
    } finally {
      setLoading(false);
    }
  };

  const resultStyle = result ? RESULT_STYLES[result.result] : null;

  return (
    <section className="pv-panel card" id="physical-verification-panel">
      <header className="pv-header">
        <h3>Physical Measurement Verification</h3>
        <span className="pv-rule-cite">LMPC Rule 22 / First Schedule</span>
      </header>

      <p className="pv-notice">
        Enter the weight or volume measured on the physical sample. The system will calculate
        the shortfall and apply the permissible tolerance — the officer confirms the result.
      </p>

      {result ? (
        <div className={`pv-result ${result.result.toLowerCase()}`}>
          <div className={`verdict-pill ${resultStyle!.cls}`}>{resultStyle!.label}</div>

          <div className="pv-result-grid">
            <div className="pv-result-row">
              <span>Declared</span>
              <strong>
                {result.declared_quantity} {result.declared_unit}
              </strong>
            </div>
            <div className="pv-result-row">
              <span>Observed</span>
              <strong>
                {result.observed_quantity} {result.observed_unit}
              </strong>
            </div>
            <div className="pv-result-row">
              <span>Shortfall (base)</span>
              <strong>
                {result.shortfall?.toFixed(2)}{" "}
                {result.tolerance_basis === "percentage" ? "(" + result.applicable_mpe?.toFixed(2) + " MPE)" : ""}
              </strong>
            </div>
            <div className="pv-result-row">
              <span>Permissible Error</span>
              <strong>{result.applicable_mpe?.toFixed(2)}</strong>
            </div>
            <div className="pv-result-row">
              <span>Rule</span>
              <strong>{result.applicable_rule_id}</strong>
            </div>
            <div className="pv-result-row">
              <span>Sample No.</span>
              <strong>#{result.sample_number}</strong>
            </div>
            {result.evidence_hash && (
              <div className="pv-result-row pv-hash">
                <span>Evidence Hash</span>
                <code title={result.evidence_hash}>{result.evidence_hash.slice(0, 16)}…</code>
              </div>
            )}
          </div>

          {result.result === "FAIL" && (
            <div className="pv-enforcement-notice">
              ⚠ Enforcement attention indicated — officer review required.
            </div>
          )}

          <button
            className="btn btn-secondary"
            onClick={() => setResult(null)}
            id="pv-new-sample-btn"
          >
            Record Another Sample
          </button>
        </div>
      ) : (
        <form className="pv-form" onSubmit={handleSubmit} id="pv-form">
          <div className="pv-form-row">
            <label htmlFor="pv-declared-qty">Declared Quantity</label>
            <div className="pv-unit-input">
              <input
                id="pv-declared-qty"
                type="text"
                value={declaredQty}
                onChange={(e) => setDeclaredQty(e.target.value)}
                placeholder="e.g. 500"
                required
              />
              <select
                id="pv-declared-unit"
                value={declaredUt}
                onChange={(e) => setDeclaredUt(e.target.value)}
                aria-label="Declared unit"
              >
                {COMMON_UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="pv-form-row">
            <label htmlFor="pv-observed-qty">Observed Quantity (field measurement)</label>
            <div className="pv-unit-input">
              <input
                id="pv-observed-qty"
                type="number"
                step="0.01"
                min="0.01"
                value={observedQty}
                onChange={(e) => setObservedQty(e.target.value)}
                placeholder="e.g. 493.5"
                required
              />
              <select
                id="pv-observed-unit"
                value={observedUt}
                onChange={(e) => setObservedUt(e.target.value)}
                aria-label="Observed unit"
              >
                {COMMON_UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="pv-form-row pv-form-row-inline">
            <div>
              <label htmlFor="pv-sample-no">Sample Number</label>
              <input
                id="pv-sample-no"
                type="number"
                min="1"
                max="99"
                value={sampleNo}
                onChange={(e) => setSampleNo(parseInt(e.target.value, 10) || 1)}
              />
            </div>
          </div>

          <div className="pv-form-row">
            <label htmlFor="pv-notes">Officer Notes (optional)</label>
            <textarea
              id="pv-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Instrument used, batch number, observations…"
            />
          </div>

          {error && <div className="pv-error" role="alert">{error}</div>}

          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            id="pv-submit-btn"
          >
            {loading ? "Calculating…" : "Verify & Commit to Evidence"}
          </button>
        </form>
      )}
    </section>
  );
}
