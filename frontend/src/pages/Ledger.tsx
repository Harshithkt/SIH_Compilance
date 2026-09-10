import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBanner, Loading, VerdictBadge, formatDateTime, shortHash } from "../components/common";
import { useI18n } from "../i18n";
import type { ChainVerification, LedgerRow } from "../types";

export default function Ledger() {
  const { t, lang } = useI18n();
  const [rows, setRows] = useState<LedgerRow[] | null>(null);
  const [verification, setVerification] = useState<ChainVerification | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    api.ledger().then(setRows).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function verify() {
    setVerifying(true);
    try {
      setVerification(await api.verifyLedger());
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setVerifying(false);
    }
  }

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!rows) return <Loading />;

  return (
    <>
      <div className="page-head">
        <h1>{t("ledger.title")}</h1>
        <p>{t("ledger.subtitle")}</p>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>
            {rows.length} {rows.length === 1 ? "entry" : "entries"}
          </h2>
          <button className="btn btn-primary btn-sm" onClick={verify} disabled={verifying}>
            {verifying ? t("ledger.verifying") : t("ledger.verify")}
          </button>
        </div>

        {verification && (
          <div style={{ padding: "12px 18px 0" }}>
            <div className={`banner ${verification.valid ? "banner-ok" : "banner-bad"}`}>
              <strong>
                {verification.valid ? "Chain intact" : `Chain broken at entry #${verification.broken_at_sequence}`}
              </strong>
              <div style={{ marginTop: 4 }}>{verification.detail}</div>
            </div>
          </div>
        )}

        {rows.length === 0 ? (
          <div className="empty">No entries yet.</div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("ledger.entry")}</th>
                  <th>{t("ledger.scan")}</th>
                  <th>Officer</th>
                  <th>Verdict</th>
                  <th>Links to</th>
                  <th>{t("ledger.hash")}</th>
                  <th>Committed</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.sequence}
                    className={
                      verification && !verification.valid && verification.broken_at_sequence === row.sequence
                        ? "broken"
                        : undefined
                    }
                    style={
                      verification && !verification.valid && verification.broken_at_sequence === row.sequence
                        ? { background: "var(--review-soft)" }
                        : undefined
                    }
                  >
                    <td>
                      <strong>#{row.sequence}</strong>
                    </td>
                    <td>
                      <Link to={`/scans/${row.scan_id}`} className="mono">
                        {row.scan_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td>{row.officer_name}</td>
                    <td>{row.verdict && <VerdictBadge verdict={row.verdict} />}</td>
                    <td className="mono muted">{shortHash(row.prev_hash, 8)}</td>
                    <td className="mono">{shortHash(row.entry_hash, 8)}</td>
                    <td className="muted">{formatDateTime(row.created_at, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="banner banner-info" style={{ marginTop: 16 }}>
        <strong>How to test this:</strong> edit any stored evidence photograph in{" "}
        <code>backend/storage/images/</code>, or change a committed verdict directly in the
        database, then run verification again. The chain reports the exact entry at which the
        record no longer matches what was committed at inspection time.
      </div>
    </>
  );
}
