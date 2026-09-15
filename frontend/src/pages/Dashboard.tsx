import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
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
  initials,
} from "../components/common";
import {
  IconArrowRight,
  IconBarChart,
  IconCamera,
  IconClock,
  IconFileText,
  IconFolder,
  IconLock,
  IconShieldCheck,
  IconSliders,
  IconUsers,
} from "../components/icons";
import { useI18n } from "../i18n";
import type { AuditEntry, Case, ChainVerification, ScanSummary, Stats, WorklistItem } from "../types";

/** The three roles do different jobs, so they get different dashboards rather than one
 *  dashboard with pieces hidden: an officer is asking "what is waiting on me", a
 *  supervisor "what is slipping", an administrator "who has access and does the record
 *  still verify". */
export default function Dashboard() {
  const { user } = useAuth();

  if (!user) return <Loading />;
  if (user.role === "admin") return <AdminDashboard />;
  if (user.role === "supervisor") return <SupervisorDashboard />;
  return <OfficerDashboard />;
}

// ---------------------------------------------------------------------------
// Officer — the work in front of me
// ---------------------------------------------------------------------------

function OfficerDashboard() {
  const { t, lang } = useI18n();
  const { user } = useAuth();

  const [stats, setStats] = useState<Stats | null>(null);
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([api.stats(), api.listScans(), api.listCases()])
      .then(([s, sc, c]) => {
        setStats(s);
        setScans(sc);
        setCases(c);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!stats || !scans || !cases) return <Loading />;

  const me = user?.full_name ?? "";
  const mine = scans.filter((s) => s.officer_name === me);
  const myPending = mine.filter((s) => s.verdict !== "GO" && !s.officer_decision);
  const myCases = cases.filter((c) => c.officer_name === me);
  const myOpenCases = myCases.filter((c) => c.status === "open" || c.status === "escalated");
  const myOverdue = myOpenCases.filter((c) => c.is_overdue);

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("dashboard.officerTitle")}</h1>
          <p>{t("dashboard.officerSubtitle")}</p>
        </div>
        <div className="page-head-actions">
          <Link to="/inspect" className="btn btn-primary btn-lg">
            <IconCamera size={16} />
            {t("nav.inspect")}
          </Link>
        </div>
      </div>

      {mine.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<IconCamera size={20} />}
            title={t("dashboard.myRecentEmpty")}
            body={t("dashboard.officerSubtitle")}
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
            <Stat accent="brand" value={mine.length} label={t("dashboard.myInspections")} />
            <Stat accent="warning" value={myPending.length} label={t("dashboard.myPending")} />
            <Stat value={myOpenCases.length} label={t("dashboard.myCases")} />
            <Stat
              accent={myOverdue.length > 0 ? "critical" : undefined}
              value={myOverdue.length}
              label={t("dashboard.myOverdue")}
            />
          </div>

          <div className="split">
            <div className="card">
              <div className="card-head">
                <h2>{t("dashboard.myReviewQueue")}</h2>
                <span className="muted">{myPending.length}</span>
              </div>
              {myPending.length === 0 ? (
                <div className="empty">{t("dashboard.myReviewEmpty")}</div>
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
                      {myPending.slice(0, 7).map((scan) => (
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

            <div className="card">
              <div className="card-head">
                <h2>{t("dashboard.myCasesDue")}</h2>
                <Link to="/cases" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                  {t("dashboard.viewAll")} <IconArrowRight size={13} />
                </Link>
              </div>
              {myOpenCases.length === 0 ? (
                <div className="empty">{t("dashboard.myCasesEmpty")}</div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("compliance.entity")}</th>
                        <th>{t("scan.status")}</th>
                        <th>{t("cases.due")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...myOpenCases]
                        .sort((a, b) => a.due_at.localeCompare(b.due_at))
                        .slice(0, 7)
                        .map((c) => (
                          <tr key={c.id} className="clickable">
                            <td>
                              <Link to={`/inspections/${c.scan_id}`}>
                                <strong>{c.product_name ?? c.scan_id.slice(0, 8)}</strong>
                              </Link>
                            </td>
                            <td>
                              <CaseStatusBadge status={c.status} />
                            </td>
                            <td>
                              <DueDate case_={c} />
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>{t("dashboard.myRecent")}</h2>
              <Link to="/inspections" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                {t("dashboard.viewAll")} <IconArrowRight size={13} />
              </Link>
            </div>
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
                  {mine.slice(0, 6).map((scan) => (
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
          </div>

          <QuickActions>
            <QuickAction
              to="/cases"
              icon={<IconFolder size={18} />}
              title={t("nav.cases")}
              sub={t("dashboard.quickCasesSub")}
            />
            <QuickAction
              to="/compliance"
              icon={<IconShieldCheck size={18} />}
              title={t("dashboard.quickCompliance")}
              sub={t("dashboard.quickCompliancesub")}
            />
            <QuickAction
              to="/evidence"
              icon={<IconLock size={18} />}
              title={t("dashboard.quickEvidence")}
              sub={t("dashboard.quickEvidenceSub")}
            />
          </QuickActions>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Supervisor — what is slipping, and who is producing what
// ---------------------------------------------------------------------------

function SupervisorDashboard() {
  const { t } = useI18n();

  const [stats, setStats] = useState<Stats | null>(null);
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [worklist, setWorklist] = useState<WorklistItem[] | null>(null);
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([api.stats(), api.listScans(), api.worklist(), api.listCases()])
      .then(([s, sc, w, c]) => {
        setStats(s);
        setScans(sc);
        setWorklist(w);
        setCases(c);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!stats || !scans || !worklist || !cases) return <Loading />;

  const escalated = cases.filter((c) => c.status === "escalated");
  const overdue = cases.filter((c) => c.is_overdue);
  const awaiting = scans.filter((s) => s.verdict !== "GO" && !s.officer_decision);
  const highPriority = worklist.filter((w) => w.repeat_offender || w.high_severity_count > 0);
  const maxClause = Math.max(...stats.top_clauses.map((c) => c.count), 1);

  // Output per officer, straight from the inspection record.
  const byOfficer = new Map<string, { total: number; pending: number }>();
  for (const scan of scans) {
    const row = byOfficer.get(scan.officer_name) ?? { total: 0, pending: 0 };
    row.total += 1;
    if (scan.verdict !== "GO" && !scan.officer_decision) row.pending += 1;
    byOfficer.set(scan.officer_name, row);
  }
  const officers = [...byOfficer.entries()].sort((a, b) => b[1].total - a[1].total);

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("dashboard.supervisorTitle")}</h1>
          <p>{t("dashboard.supervisorSubtitle")}</p>
        </div>
        <div className="page-head-actions">
          <Link to="/cases?status=escalated" className="btn btn-primary btn-lg">
            <IconFolder size={16} />
            {t("dashboard.needsDecision")}
          </Link>
        </div>
      </div>

      <div className="stack">
        <div className="stat-row">
          <Stat
            accent={escalated.length > 0 ? "critical" : undefined}
            value={escalated.length}
            label={t("dashboard.statEscalatedMine")}
          />
          <Stat
            accent={overdue.length > 0 ? "critical" : undefined}
            value={overdue.length}
            label={t("dashboard.statOverdue")}
          />
          <Stat accent="warning" value={awaiting.length} label={t("dashboard.statAwaiting")} />
          <Stat accent="critical" value={highPriority.length} label={t("dashboard.statPriority")} />
          <Stat accent="brand" value={stats.total_scans} label={t("dashboard.statInspections")} />
        </div>

        <div className="card">
          <div className="card-head">
            <div className="card-head-text">
              <h2>{t("dashboard.needsDecision")}</h2>
              <p>{t("case.status.escalated")}</p>
            </div>
            <Link to="/cases?status=escalated" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
              {t("dashboard.viewAll")} <IconArrowRight size={13} />
            </Link>
          </div>
          {escalated.length === 0 ? (
            <div className="empty">{t("dashboard.needsDecisionEmpty")}</div>
          ) : (
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
          )}
        </div>

        <div className="split">
          <div className="card">
            <div className="card-head">
              <h2>{t("dashboard.teamActivity")}</h2>
              <span className="muted">{officers.length}</span>
            </div>
            {officers.length === 0 ? (
              <div className="empty">{t("dashboard.teamActivityEmpty")}</div>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("scan.officer")}</th>
                      <th>{t("report.inspections")}</th>
                      <th>{t("dashboard.statAwaiting")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {officers.map(([name, row]) => (
                      <tr key={name}>
                        <td>
                          <div className="row" style={{ gap: 9, flexWrap: "nowrap" }}>
                            <span
                              className="officer-avatar"
                              style={{ width: 26, height: 26, fontSize: 10.5 }}
                            >
                              {initials(name)}
                            </span>
                            <strong>{name}</strong>
                          </div>
                        </td>
                        <td>
                          <strong>{row.total}</strong>
                        </td>
                        <td>
                          {row.pending > 0 ? (
                            <span className="tag tag-medium">{row.pending}</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
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
                <h2>{t("dashboard.riskiest")}</h2>
                <Link to="/compliance" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                  {t("dashboard.viewAll")} <IconArrowRight size={13} />
                </Link>
              </div>
              {worklist.length === 0 ? (
                <div className="empty">{t("compliance.empty")}</div>
              ) : (
                <div className="stack" style={{ gap: 0 }}>
                  {worklist.slice(0, 5).map((item) => (
                    <Link
                      key={item.entity.id}
                      to={`/entities/${item.entity.id}`}
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
                          {item.entity.name}
                        </strong>
                        {item.repeat_offender && (
                          <span className="tag tag-high">{t("compliance.repeat")}</span>
                        )}
                      </span>
                      <strong>{item.risk_score}</strong>
                    </Link>
                  ))}
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

        <QuickActions>
          <QuickAction
            to="/cases"
            icon={<IconFolder size={18} />}
            title={t("nav.cases")}
            sub={t("dashboard.quickCasesSub")}
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
            to="/audit"
            icon={<IconClock size={18} />}
            title={t("nav.audit")}
            sub={t("dashboard.quickAuditSub")}
          />
        </QuickActions>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Administrator — access, configuration, integrity
// ---------------------------------------------------------------------------

function AdminDashboard() {
  const { t, lang } = useI18n();

  const [accounts, setAccounts] = useState<{ username: string; full_name: string; role: string; is_active: boolean }[] | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<{
    active_rule_version: string;
    text_recognition_provider: string;
    vision_model: string;
  } | null>(null);
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([api.listUsers(), api.auditLog(20), api.stats(), api.health()])
      .then(([u, a, s, h]) => {
        setAccounts(u);
        setAudit(a);
        setStats(s);
        setHealth(h);
      })
      .catch((e) => setError(e.message));
    // Verification recomputes the whole chain, so it lands on its own rather than
    // holding the rest of the page behind it.
    api.verifyLedger().then(setChain).catch(() => setChain(null));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!accounts || !audit || !stats || !health) return <Loading />;

  const active = accounts.filter((a) => a.is_active);

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("dashboard.adminTitle")}</h1>
          <p>{t("dashboard.adminSubtitle")}</p>
        </div>
        <div className="page-head-actions">
          <Link to="/team" className="btn btn-primary btn-lg">
            <IconUsers size={16} />
            {t("nav.team")}
          </Link>
        </div>
      </div>

      <div className="stack">
        <div className="stat-row">
          <Stat accent="brand" value={accounts.length} label={t("dashboard.statAccounts")} />
          <Stat accent="good" value={active.length} label={t("dashboard.statActive")} />
          <Stat value={stats.total_scans} label={t("dashboard.statInspections")} />
          <Stat
            accent={chain ? (chain.valid ? "good" : "critical") : undefined}
            value={chain ? (chain.valid ? t("dashboard.chainIntact") : t("dashboard.chainBroken")) : "…"}
            label={t("dashboard.statChain")}
          />
        </div>

        {chain && !chain.valid && (
          <div className="banner banner-bad">
            <strong>
              {t("dashboard.chainBroken")} — #{chain.broken_at_sequence}
            </strong>
            <div style={{ marginTop: 4 }}>{chain.detail}</div>
          </div>
        )}

        <div className="split">
          <div className="card">
            <div className="card-head">
              <h2>{t("dashboard.accounts")}</h2>
              <Link to="/team" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                {t("dashboard.viewAll")} <IconArrowRight size={13} />
              </Link>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("team.account")}</th>
                    <th>{t("team.role")}</th>
                    <th>{t("team.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.username}>
                      <td>
                        <div className="row" style={{ gap: 9, flexWrap: "nowrap" }}>
                          <span
                            className="officer-avatar"
                            style={{ width: 26, height: 26, fontSize: 10.5 }}
                          >
                            {initials(account.full_name)}
                          </span>
                          <span style={{ minWidth: 0 }}>
                            <strong style={{ display: "block", fontSize: 13 }}>
                              {account.full_name}
                            </strong>
                            <span className="mono muted">{account.username}</span>
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="role-pill">
                          {t(`auth.role.${account.role}` as never)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${account.is_active ? "badge-good" : "badge-muted"}`}>
                          {account.is_active ? t("team.active") : t("team.inactive")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>{t("dashboard.recentActivity")}</h2>
              <Link to="/audit" className="row" style={{ fontSize: 12.5, fontWeight: 650 }}>
                {t("dashboard.viewAudit")} <IconArrowRight size={13} />
              </Link>
            </div>
            {audit.length === 0 ? (
              <div className="empty">{t("dashboard.recentActivityEmpty")}</div>
            ) : (
              <div className="stack" style={{ gap: 0 }}>
                {audit.slice(0, 8).map((entry) => (
                  <div
                    key={entry.id}
                    className="row"
                    style={{
                      justifyContent: "space-between",
                      padding: "10px 18px",
                      borderBottom: "1px solid var(--line-2)",
                    }}
                  >
                    <span style={{ minWidth: 0 }}>
                      <strong style={{ display: "block", fontSize: 13 }}>
                        {entry.actor_username}
                      </strong>
                      <span className="mono muted">{entry.action}</span>
                    </span>
                    <span className="muted" style={{ fontSize: 11.5 }}>
                      {formatDateTime(entry.created_at, lang)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="card card-pad">
          <h2 style={{ marginBottom: 12 }}>{t("dashboard.systemConfig")}</h2>
          <dl className="dl">
            <dt>{t("dashboard.configRules")}</dt>
            <dd className="mono">{health.active_rule_version}</dd>
            <dt>{t("dashboard.configProvider")}</dt>
            <dd>
              <code>{health.text_recognition_provider}</code>
            </dd>
            <dt>{t("dashboard.configModel")}</dt>
            <dd className="mono">{health.vision_model}</dd>
          </dl>
        </div>

        <QuickActions>
          <QuickAction
            to="/team"
            icon={<IconUsers size={18} />}
            title={t("nav.team")}
            sub={t("dashboard.quickTeamSub")}
          />
          <QuickAction
            to="/audit"
            icon={<IconClock size={18} />}
            title={t("nav.audit")}
            sub={t("dashboard.quickAuditSub")}
          />
          <QuickAction
            to="/evidence"
            icon={<IconLock size={18} />}
            title={t("dashboard.quickEvidence")}
            sub={t("dashboard.quickEvidenceSub")}
          />
          <QuickAction
            to="/rules"
            icon={<IconSliders size={18} />}
            title={t("nav.rules")}
            sub={t("settings.rulePack")}
          />
          <QuickAction
            to="/analytics"
            icon={<IconBarChart size={18} />}
            title={t("nav.analytics")}
            sub={t("dashboard.quickAnalyticsSub")}
          />
        </QuickActions>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Shared pieces
// ---------------------------------------------------------------------------

function QuickActions({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="card">
      <div className="card-head">
        <h2>{t("dashboard.quickActions")}</h2>
      </div>
      <div
        className="card-pad"
        style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}
      >
        {children}
      </div>
    </div>
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
        flexWrap: "nowrap",
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
