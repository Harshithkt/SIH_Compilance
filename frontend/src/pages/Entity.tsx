import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import {
  ClauseTag,
  ErrorBanner,
  Loading,
  Stat,
  VerdictBadge,
  formatDateTime,
} from "../components/common";
import { useI18n } from "../i18n";
import type { EntityDetail } from "../types";

export default function Entity() {
  const { entityId } = useParams<{ entityId: string }>();
  const { t, lang } = useI18n();
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) return;
    api.entity(entityId).then(setDetail).catch((e) => setError(e.message));
  }, [entityId]);

  if (error) return <ErrorBanner message={error} />;
  if (!detail) return <Loading />;

  const { entity } = detail;
  const maxClause = Math.max(...detail.top_clauses.map((c) => c.count), 1);

  return (
    <>
      <div className="page-head">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h1>{entity.name}</h1>
            <p>
              <Link to="/worklist">{t("nav.worklist")}</Link>
              {entity.address ? ` · ${entity.address}` : ""}
            </p>
          </div>
          {detail.repeat_offender && (
            <span className="tag tag-high" style={{ fontSize: 12, padding: "5px 10px" }}>
              {t("worklist.repeat")}
            </span>
          )}
        </div>
      </div>

      <div className="stat-row" style={{ marginBottom: 16 }}>
        <Stat value={detail.risk_score} label={t("worklist.risk")} />
        <Stat value={detail.scan_count} label={t("worklist.scans")} />
        <Stat value={detail.violation_count} label={t("worklist.violations")} />
        <Stat value={detail.high_severity_count} label="High severity" />
      </div>

      <div className="split">
        <div className="card">
          <div className="card-head">
            <h2>Inspections of this entity</h2>
            <span className="muted">{detail.scans.length}</span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Commodity</th>
                  <th>Verdict</th>
                  <th>Rules applied</th>
                  <th>Captured</th>
                </tr>
              </thead>
              <tbody>
                {detail.scans.map((scan) => (
                  <tr key={scan.id}>
                    <td>
                      <Link to={`/scans/${scan.id}`}>
                        <strong>{scan.product_name ?? scan.id.slice(0, 8)}</strong>
                      </Link>
                    </td>
                    <td>
                      <VerdictBadge verdict={scan.verdict} />
                    </td>
                    <td className="mono muted">{scan.rule_version}</td>
                    <td className="muted">{formatDateTime(scan.captured_at, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <div className="card-head">
              <h2>{t("worklist.clauses")}</h2>
            </div>
            <div className="card-pad stack" style={{ gap: 9 }}>
              {detail.top_clauses.length === 0 ? (
                <span className="muted">No contraventions recorded.</span>
              ) : (
                detail.top_clauses.map((clause) => (
                  <div key={clause.clause} className="row" style={{ gap: 10 }}>
                    <div style={{ minWidth: 150 }}>
                      <ClauseTag clause={clause.clause} />
                    </div>
                    <div className="risk-bar" style={{ flex: 1 }}>
                      <span style={{ width: `${(clause.count / maxClause) * 100}%` }} />
                    </div>
                    <strong>{clause.count}</strong>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="card card-pad">
            <h2 style={{ marginBottom: 8 }}>Registration details on the pack</h2>
            <dl className="dl">
              <dt>FSSAI licence</dt>
              <dd>{entity.fssai_no ?? <span className="muted">not declared</span>}</dd>
              <dt>Licence no.</dt>
              <dd>{entity.license_no ?? <span className="muted">not declared</span>}</dd>
              <dt>Address</dt>
              <dd>{entity.address ?? <span className="muted">not declared</span>}</dd>
            </dl>
            <p className="muted" style={{ marginBottom: 0, fontSize: 12 }}>
              These are the particulars printed on the inspected packages, as read by the system.
              They are not verified against any external register.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
