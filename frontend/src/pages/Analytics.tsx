import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { EmptyState, ErrorBanner, Loading, Stat } from "../components/common";
import { IconBarChart, IconCamera } from "../components/icons";
import { useI18n } from "../i18n";
import type { Stats, Verdict } from "../types";
import { Link } from "react-router-dom";

// Fixed status hues — the same four colours the verdict badges use, so a bar here
// means exactly what the badge means elsewhere. Never reused for anything else.
const VERDICT_COLOR: Record<Verdict, string> = {
  GO: "#0ca30c",
  FIX: "#f2a900",
  REVIEW: "#d03b3b",
  PENDING: "#8a8f98",
};

const CLAUSE_COLOR = "#2a78d6";

// Recharts calls this as (value, index) — a second parameter here would silently be
// overridden by the tick's index, not a caller-supplied default, so the limit is fixed.
function truncateClause(clause: string): string {
  const max = 20;
  return clause.length > max ? `${clause.slice(0, max - 1)}…` : clause;
}

export default function Analytics() {
  const { t } = useI18n();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    api.stats().then(setStats).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!stats) return <Loading />;

  if (stats.total_scans === 0) {
    return (
      <>
        <div className="page-head">
          <div className="page-head-text">
            <h1>{t("analytics.title")}</h1>
            <p>{t("analytics.subtitle")}</p>
          </div>
        </div>
        <div className="card">
          <EmptyState
            icon={<IconBarChart size={18} />}
            title={t("analytics.noData")}
            action={
              <Link to="/inspect" className="btn btn-primary">
                <IconCamera size={15} />
                {t("common.startInspection")}
              </Link>
            }
          />
        </div>
      </>
    );
  }

  const verdictOrder: Verdict[] = ["GO", "FIX", "REVIEW", "PENDING"];
  const verdictData = verdictOrder.map((v) => ({
    verdict: v,
    label: t(`verdict.${v}` as never),
    count: stats.verdicts[v] ?? 0,
  }));

  const clauseData = stats.top_clauses
    .slice(0, 8)
    .map((c) => ({ clause: c.clause, count: c.count }))
    .reverse();

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("analytics.title")}</h1>
          <p>{t("analytics.subtitle")}</p>
        </div>
      </div>

      <div className="stat-row" style={{ marginBottom: 16 }}>
        <Stat accent="brand" value={stats.total_scans} label="Inspections" />
        <Stat value={stats.entities_tracked} label="Entities tracked" />
        <Stat accent="critical" value={stats.total_violations} label="Findings" />
        <Stat value={stats.top_clauses.length} label="Distinct clauses breached" />
      </div>

      <div className="split">
        <div className="card">
          <div className="card-head">
            <h2>{t("analytics.verdictDistribution")}</h2>
          </div>
          <div className="card-pad" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={verdictData} margin={{ top: 16, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#edece8" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "#757a82" }}
                  axisLine={{ stroke: "#e1dfda" }}
                  tickLine={false}
                />
                <YAxis hide />
                <Tooltip
                  cursor={{ fill: "#faf9f7" }}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--surface)",
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={64}>
                  {verdictData.map((entry) => (
                    <Cell key={entry.verdict} fill={VERDICT_COLOR[entry.verdict]} />
                  ))}
                  <LabelList dataKey="count" position="top" style={{ fontSize: 12, fontWeight: 700, fill: "#16171b" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>{t("analytics.topClauses")}</h2>
          </div>
          <div className="card-pad" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={clauseData}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 0, bottom: 0 }}
              >
                <CartesianGrid horizontal={false} stroke="#edece8" />
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="clause"
                  width={132}
                  tickFormatter={truncateClause}
                  tick={{ fontSize: 10.5, fill: "#494d54", fontFamily: "ui-monospace, monospace" }}
                  axisLine={{ stroke: "#e1dfda" }}
                  tickLine={false}
                  interval={0}
                />
                <Tooltip
                  cursor={{ fill: "#faf9f7" }}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--surface)",
                  }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} fill={CLAUSE_COLOR} maxBarSize={16}>
                  <LabelList dataKey="count" position="right" style={{ fontSize: 11, fontWeight: 700, fill: "#16171b" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </>
  );
}
