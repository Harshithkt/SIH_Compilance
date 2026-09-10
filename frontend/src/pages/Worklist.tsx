import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ClauseTag, ErrorBanner, Loading, Stat, VerdictBadge } from "../components/common";
import { useI18n } from "../i18n";
import type { Stats, WorklistItem } from "../types";

export default function Worklist() {
  const { t } = useI18n();
  const [items, setItems] = useState<WorklistItem[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([api.worklist(), api.stats()])
      .then(([worklist, statistics]) => {
        setItems(worklist);
        setStats(statistics);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!items || !stats) return <Loading />;

  const maxRisk = Math.max(...items.map((i) => i.risk_score), 1);

  return (
    <>
      <div className="page-head">
        <h1>{t("worklist.title")}</h1>
        <p>{t("worklist.subtitle")}</p>
      </div>

      <div className="stat-row" style={{ marginBottom: 16 }}>
        <Stat value={stats.total_scans} label="Inspections" />
        <Stat value={stats.entities_tracked} label="Entities tracked" />
        <Stat value={stats.total_violations} label="Findings" />
        <Stat value={stats.verdicts.REVIEW ?? 0} label="For action" />
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("worklist.entity")}</h2>
          <span className="muted">{items.length}</span>
        </div>

        {items.length === 0 ? (
          <div className="empty">{t("worklist.empty")}</div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t("worklist.entity")}</th>
                  <th>{t("worklist.risk")}</th>
                  <th>{t("worklist.scans")}</th>
                  <th>{t("worklist.violations")}</th>
                  <th>{t("worklist.clauses")}</th>
                  <th>Latest</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, index) => (
                  <tr key={item.entity.id}>
                    <td className="muted">{index + 1}</td>
                    <td>
                      <Link to={`/entities/${item.entity.id}`}>
                        <strong>{item.entity.name}</strong>
                      </Link>
                      {item.repeat_offender && (
                        <span className="tag tag-high" style={{ marginLeft: 7 }}>
                          {t("worklist.repeat")}
                        </span>
                      )}
                      {item.entity.address && (
                        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                          {item.entity.address}
                        </div>
                      )}
                    </td>
                    <td>
                      <strong>{item.risk_score}</strong>
                      <div className="risk-bar" style={{ marginTop: 4 }}>
                        <span style={{ width: `${(item.risk_score / maxRisk) * 100}%` }} />
                      </div>
                    </td>
                    <td>{item.scan_count}</td>
                    <td>
                      {item.violation_count}
                      {item.high_severity_count > 0 && (
                        <span className="tag tag-high" style={{ marginLeft: 6 }}>
                          {item.high_severity_count} high
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {item.top_clauses.map((clause) => (
                          <span key={clause.clause} title={`${clause.count} findings`}>
                            <ClauseTag clause={`${clause.clause} ×${clause.count}`} />
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>{item.latest_verdict && <VerdictBadge verdict={item.latest_verdict} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {stats.top_clauses.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-head">
            <h2>Most-breached clauses across all inspections</h2>
          </div>
          <div className="card-pad stack" style={{ gap: 9 }}>
            {stats.top_clauses.map((clause) => (
              <div key={clause.clause} className="row" style={{ gap: 12 }}>
                <div style={{ minWidth: 210 }}>
                  <ClauseTag clause={clause.clause} />
                </div>
                <div className="risk-bar" style={{ flex: 1 }}>
                  <span
                    style={{
                      width: `${(clause.count / stats.top_clauses[0].count) * 100}%`,
                      background: "var(--accent)",
                    }}
                  />
                </div>
                <strong style={{ minWidth: 22, textAlign: "right" }}>{clause.count}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
