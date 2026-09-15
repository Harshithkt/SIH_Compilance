import { useEffect, useState } from "react";
import { api } from "../api";
import { ClauseTag, ErrorBanner, Loading, Stat } from "../components/common";
import { IconDownload, IconPrinter } from "../components/icons";
import { useI18n } from "../i18n";
import type { MonthlyReport } from "../types";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export default function Report() {
  const { t } = useI18n();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReport(null);
    setError(null);
    api.monthlyReport(year, month).then(setReport).catch((e) => setError(e.message));
  }, [year, month]);

  const years = [now.getFullYear(), now.getFullYear() - 1, now.getFullYear() - 2];

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("report.title")}</h1>
          <p>{t("report.subtitle")}</p>
        </div>
      </div>

      <div className="print-only" style={{ marginBottom: 16 }}>
        <strong style={{ fontSize: 16 }}>LabelLens — Legal Metrology enforcement</strong>
        {report && (
          <div className="muted" style={{ fontSize: 12 }}>
            {report.period.label} · generated {new Date(report.generated_at).toLocaleString("en-IN")}
          </div>
        )}
      </div>

      <div className="card no-print" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <div className="row">
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              style={{ maxWidth: 160 }}
            >
              {MONTHS.map((name, index) => (
                <option key={name} value={index + 1}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              style={{ maxWidth: 110 }}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
          {report && (
            <div className="row">
              <button className="btn btn-sm" onClick={() => window.print()}>
                <IconPrinter size={14} />
                {t("report.print")}
              </button>
              <button
                className="btn btn-sm"
                onClick={() =>
                  api
                    .downloadMonthlyReport(year, month)
                    .catch((e) => setError(e instanceof Error ? e.message : t("common.error")))
                }
              >
                <IconDownload size={14} />
                {t("report.raw")}
              </button>
            </div>
          )}
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {!report && !error && <Loading />}

      {report && (
        <div className="stack">
          <div className="stat-row">
            <Stat value={report.totals.inspections} label={t("report.inspections")} />
            <Stat
              value={`${Math.round(report.totals.non_compliance_rate * 100)}%`}
              label={t("report.rate")}
            />
            <Stat value={report.totals.findings} label={t("compliance.violations")} />
            <Stat value={report.totals.entities_with_findings} label={t("report.entities")} />
            <Stat value={report.totals.pending_response} label="Within response window" />
          </div>

          <div
            className={`banner ${report.evidence_integrity.valid ? "banner-ok" : "banner-bad"}`}
          >
            <strong>
              {report.evidence_integrity.valid
                ? "Evidence integrity verified"
                : `Evidence integrity FAILED at ledger entry #${report.evidence_integrity.broken_at_sequence}`}
            </strong>
            <div style={{ marginTop: 4 }}>{report.evidence_integrity.detail}</div>
          </div>

          {report.totals.inspections === 0 ? (
            <div className="card">
              <div className="empty">No inspections were recorded in {report.period.label}.</div>
            </div>
          ) : (
            <div className="split">
              <div className="card">
                <div className="card-head">
                  <h2>{t("report.clauses")}</h2>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Clause</th>
                        <th>Requirement</th>
                        <th>Findings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.clause_breakdown.map((row) => (
                        <tr key={row.clause}>
                          <td>
                            <ClauseTag clause={row.clause} />
                          </td>
                          <td>{row.title}</td>
                          <td>
                            <strong>{row.count}</strong>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="stack">
                <div className="card">
                  <div className="card-head">
                    <h2>{t("report.priority")}</h2>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Entity</th>
                          <th>Risk</th>
                          <th>Findings</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.priority_entities.map((entity) => (
                          <tr key={entity.name}>
                            <td>
                              <strong>{entity.name}</strong>
                              {entity.repeat_offender && (
                                <span className="tag tag-high" style={{ marginLeft: 6 }}>
                                  repeat
                                </span>
                              )}
                            </td>
                            <td>{entity.risk_score}</td>
                            <td>{entity.findings_in_period}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="card">
                  <div className="card-head">
                    <h2>{t("report.officers")}</h2>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <tbody>
                        {report.inspections_by_officer.map((row) => (
                          <tr key={row.officer}>
                            <td>{row.officer}</td>
                            <td>
                              <strong>{row.inspections}</strong>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="card card-pad">
                  <h3 style={{ marginBottom: 6 }}>{t("report.versions")}</h3>
                  <div className="row">
                    {Object.entries(report.rule_versions_applied).map(([version, count]) => (
                      <span key={version} className="tag">
                        {version} × {count}
                      </span>
                    ))}
                  </div>
                  <p className="muted" style={{ marginBottom: 0, marginTop: 10, fontSize: 12 }}>
                    {report.note}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
