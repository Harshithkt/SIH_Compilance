import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import {
  EmptyState,
  ErrorBanner,
  Loading,
  Timeline,
  TimelineItem,
  VerdictBadge,
  formatDateTime,
  shortHash,
} from "../components/common";
import { IconCheckCircle, IconLock } from "../components/icons";
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
        <div className="page-head-text">
          <h1>{t("evidence.title")}</h1>
          <p>{t("evidence.subtitle")}</p>
        </div>
        <div className="page-head-actions">
          <button className="btn btn-primary" onClick={verify} disabled={verifying}>
            <IconLock size={15} />
            {verifying ? t("evidence.verifying") : t("evidence.verify")}
          </button>
        </div>
      </div>

      {verification && (
        <div
          className={`banner ${verification.valid ? "banner-ok" : "banner-bad"}`}
          style={{ marginBottom: 16 }}
        >
          <strong>
            {verification.valid ? "Chain intact" : `Chain broken at entry #${verification.broken_at_sequence}`}
          </strong>
          <div style={{ marginTop: 4 }}>{verification.detail}</div>
        </div>
      )}

      <div className="card">
        <div className="card-head">
          <h2>
            {rows.length} {rows.length === 1 ? "entry" : "entries"}
          </h2>
        </div>

        {rows.length === 0 ? (
          <EmptyState icon={<IconLock size={18} />} title={t("evidence.empty")} />
        ) : (
          <Timeline>
            {rows.map((row, index) => {
              const broken =
                !!verification && !verification.valid && verification.broken_at_sequence === row.sequence;
              return (
                <TimelineItem key={row.sequence} last={index === rows.length - 1} bad={broken}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <div className="row" style={{ gap: 10 }}>
                      <strong>#{row.sequence}</strong>
                      {row.verdict && <VerdictBadge verdict={row.verdict} />}
                      {broken && <span className="tag tag-high">Chain break</span>}
                    </div>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {formatDateTime(row.created_at, lang)}
                    </span>
                  </div>
                  <div className="row" style={{ marginTop: 6, fontSize: 12.5 }}>
                    <Link to={`/inspections/${row.scan_id}`}>
                      {t("evidence.scan")} {row.scan_id.slice(0, 8)}
                    </Link>
                    <span className="muted">· {row.officer_name}</span>
                  </div>
                  <div className="chain-link" style={{ marginTop: 6 }}>
                    <span className="muted">prev</span>
                    <span className="mono muted">{shortHash(row.prev_hash, 8)}</span>
                    <span className="muted">→</span>
                    <span className="muted">{t("evidence.hash").toLowerCase()}</span>
                    <span className="mono">{shortHash(row.entry_hash, 8)}</span>
                  </div>
                </TimelineItem>
              );
            })}
          </Timeline>
        )}
      </div>

      <div className="banner banner-info row" style={{ marginTop: 16, gap: 8 }}>
        <IconCheckCircle size={16} />
        <span>
          <strong>{t("evidence.howToTest")}:</strong> {t("evidence.howToTestBody")}
        </span>
      </div>
    </>
  );
}
