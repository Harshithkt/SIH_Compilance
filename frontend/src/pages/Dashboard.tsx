import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import {
  CaseStatusBadge,
  CaseTrackTag,
  ClauseTag,
  DueDate,
  EmptyState,
  ErrorBanner,
  Loading,
  Stat,
  VerdictBadge,
  formatDateTime,
} from "../components/common";
import {
  IconArrowRight,
  IconBarChart,
  IconCamera,
  IconFileText,
  IconFolder,
  IconLock,
  IconShieldCheck,
} from "../components/icons";
import { useI18n } from "../i18n";
import type { Case, ScanSummary, Stats, WorklistItem } from "../types";

export default function Dashboard() {
  const { t, lang } = useI18n();
  const [stats, setStats] = useState<Stats | null>(null);
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [worklist, setWorklist] = useState<WorklistItem[] | null>(null);
  const [escalated, setEscalated] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([api.stats(), api.listScans(), api.worklist(), api.listCases({ status: "escalated" })])
      .then(([s, sc, w, cases]) => {
        setStats(s);
        setScans(sc);
        setWorklist(w);
        setEscalated(cases);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!stats || !scans || !worklist || !escalated) return <Loading />;

  const recent = scans.slice(0, 6);
  const pendingAll = scans.filter((s) => s.verdict !== "GO" && !s.officer_decision);
  const pending = pendingAll.slice(0, 6);
  const highPriority = worklist.filter((w) => w.repeat_offender || w.high_severity_count > 0);
  const maxClause = Math.max(...stats.top_clauses.map((c) => c.count), 1);

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("dashboard.title")}</h1>
          <p>{t("dashboard.subtitle")}</p>
        </div>
        <div className="page-head-actions">
          <Link to="/inspect" className="btn btn-primary btn-lg">
            <IconCamera size={16} />
            {t("nav.inspect")}
          </Link>
        </div>
      </div>

      {stats.total_scans === 0 ? (
        <div className="card">
          <EmptyState
            icon={<IconCamera size={20} />}
            title={t("dashboard.recentEmpty")}
            body="Run the first inspection to start building the compliance record."
            action={
              <Link to="/inspect" className="btn btn-primary">
                {t("common.startInspection")}
              </Link>
            }
          />
        </div>
      ) : (
        <div className="stack">
          <div className="stat-row">
            <Stat accent="brand" value={stats.total_scans} label={t("dashboard.statInspections")} />
            <Stat accent="warning" value={stats.pending_review} label={t("dashboard.statPending")} />
            <Stat
              accent="critical"
              value={stats.verdicts.REVIEW ?? 0}
              label={t("dashboard.statViolations")}
            />
            <Stat accent="critical" value={highPriority.length} label={t("dashboard.statPriority")} />
            <Stat accent="critical" value={stats.cases.escalated} label={t("dashboard.statEscalated")} />
          </div>

          {escalated.length > 0 && (
            <div className="card">
              <div className="card-head">
                <div className="card-head-text">
                  <h2>{t("dashboard.attention")}</h2>
                </div>
                <Link to="/cases?status=escalated" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                  {t("dashboard.viewAll")} <IconArrowRight size={13} />
                </Link>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("compliance.entity")}</th>
                      <th>{t("case.track.formal_case")}</th>
                      <th>{t("case.owner")}</th>
                      <th>{t("cases.due")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {escalated.slice(0, 6).map((c) => (
                      <tr key={c.id} className="clickable">
                        <td>
                          <Link to={`/inspections/${c.scan_id}`}>
                            <strong>{c.product_name ?? c.scan_id.slice(0, 8)}</strong>
                          </Link>
                          {c.entity_name && (
                            <div className="muted" style={{ fontSize: 12 }}>
                              {c.entity_name}
                            </div>
                          )}
                        </td>
                        <td>
                          <CaseTrackTag track={c.track} /> <CaseStatusBadge status={c.status} />
                        </td>
                        <td>{c.officer_name}</td>
                        <td>
                          <DueDate case_={c} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="split">
            <div className="card">
              <div className="card-head">
                <h2>{t("dashboard.recent")}</h2>
                <Link to="/inspections" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                  {t("dashboard.viewAll")} <IconArrowRight size={13} />
                </Link>
              </div>
              {recent.length === 0 ? (
                <div className="empty">{t("dashboard.recentEmpty")}</div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("scans.title")}</th>
                        <th>{t("scan.status")}</th>
                        <th>{t("scan.capturedAt")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recent.map((scan) => (
                        <tr key={scan.id} className="clickable">
                          <td>
                            <Link to={`/inspections/${scan.id}`}>
                              <strong>{scan.product_name ?? scan.id.slice(0, 8)}</strong>
                            </Link>
                          </td>
                          <td>
                            <VerdictBadge verdict={scan.verdict} />
                          </td>
                          <td className="muted">{formatDateTime(scan.captured_at, lang)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="stack">
              <div className="card">
                <div className="card-head">
                  <h2>{t("dashboard.pending")}</h2>
                  <span className="muted">{pendingAll.length}</span>
                </div>
                {pending.length === 0 ? (
                  <div className="empty">{t("dashboard.pendingEmpty")}</div>
                ) : (
                  <div className="stack" style={{ gap: 0 }}>
                    {pending.map((scan) => (
                      <Link
                        key={scan.id}
                        to={`/inspections/${scan.id}`}
                        className="row"
                        style={{
                          justifyContent: "space-between",
                          padding: "10px 18px",
                          borderBottom: "1px solid var(--line-2)",
                          color: "inherit",
                        }}
                      >
                        <span style={{ minWidth: 0 }}>
                          <strong style={{ display: "block", fontSize: 13 }}>
                            {scan.product_name ?? scan.id.slice(0, 8)}
                          </strong>
                          <span className="muted" style={{ fontSize: 11.5 }}>
                            {formatDateTime(scan.captured_at, lang)}
                          </span>
                        </span>
                        <VerdictBadge verdict={scan.verdict} />
                      </Link>
                    ))}
                    {pendingAll.length > pending.length && (
                      <Link
                        to="/inspections"
                        style={{ display: "block", padding: "9px 18px", fontSize: 12, fontWeight: 650 }}
                      >
                        +{pendingAll.length - pending.length} more in {t("nav.inspections")}
                      </Link>
                    )}
                  </div>
                )}
              </div>

              <div className="card">
                <div className="card-head">
                  <h2>{t("dashboard.findings")}</h2>
                </div>
                {stats.top_clauses.length === 0 ? (
                  <div className="empty">{t("dashboard.findingsEmpty")}</div>
                ) : (
                  <div className="card-pad stack" style={{ gap: 9 }}>
                    {stats.top_clauses.slice(0, 5).map((clause) => (
                      <div key={clause.clause} className="row" style={{ gap: 10 }}>
                        <div style={{ minWidth: 130 }}>
                          <ClauseTag clause={clause.clause} />
                        </div>
                        <div className="risk-bar" style={{ flex: 1 }}>
                          <span style={{ width: `${(clause.count / maxClause) * 100}%` }} />
                        </div>
                        <strong style={{ minWidth: 18, textAlign: "right" }}>{clause.count}</strong>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>{t("dashboard.quickActions")}</h2>
            </div>
            <div className="card-pad" style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
              <QuickAction
                to="/cases"
                icon={<IconFolder size={18} />}
                title={t("nav.cases")}
                sub={t("cases.subtitle")}
              />
              <QuickAction
                to="/compliance"
                icon={<IconShieldCheck size={18} />}
                title={t("dashboard.quickCompliance")}
                sub={t("dashboard.quickCompliancesub")}
              />
              <QuickAction
                to="/reports"
                icon={<IconFileText size={18} />}
                title={t("dashboard.quickReports")}
                sub={t("dashboard.quickReportsSub")}
              />
              <QuickAction
                to="/evidence"
                icon={<IconLock size={18} />}
                title={t("dashboard.quickEvidence")}
                sub={t("dashboard.quickEvidenceSub")}
              />
              <QuickAction
                to="/analytics"
                icon={<IconBarChart size={18} />}
                title={t("nav.analytics")}
                sub={t("analytics.subtitle")}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function QuickAction({
  to,
  icon,
  title,
  sub,
}: {
  to: string;
  icon: ReactNode;
  title: string;
  sub: string;
}) {
  return (
    <Link
      to={to}
      className="row"
      style={{
        gap: 12,
        padding: "12px 14px",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius)",
        color: "inherit",
        alignItems: "flex-start",
      }}
    >
      <span
        style={{
          color: "var(--brand-ink)",
          background: "var(--brand-soft)",
          borderRadius: "var(--radius-sm)",
          width: 34,
          height: 34,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
        }}
      >
        {icon}
      </span>
      <span style={{ minWidth: 0 }}>
        <strong style={{ display: "block", fontSize: 13 }}>{title}</strong>
        <span className="muted" style={{ fontSize: 11.5 }}>
          {sub}
        </span>
      </span>
    </Link>
  );
}
