import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import {
  ClauseTag,
  ErrorBanner,
  LabelViewer,
  Loading,
  SeverityTag,
  VerdictBadge,
  formatDateTime,
  shortHash,
} from "../components/common";
import { fieldLabel, useI18n } from "../i18n";
import type { RuleDiff, RuleVersionSummary, Scan } from "../types";

export default function ScanDetail() {
  const { scanId } = useParams<{ scanId: string }>();
  const { t, lang } = useI18n();

  const [scan, setScan] = useState<Scan | null>(null);
  const [versions, setVersions] = useState<RuleVersionSummary[]>([]);
  const [diff, setDiff] = useState<RuleDiff | null>(null);
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [explaining, setExplaining] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    setError(null);
    api.getScan(scanId).then(setScan).catch((e) => setError(e.message));
    api
      .ruleVersions()
      .then((r) => setVersions(r.versions))
      .catch(() => setVersions([]));
  }, [scanId]);

  async function explain(violationId: string) {
    if (!scanId) return;
    setExplaining(violationId);
    try {
      const result = await api.explainViolation(scanId, violationId, lang);
      setExplanations((prev) => ({ ...prev, [violationId]: result.explanation }));
    } catch (e) {
      setExplanations((prev) => ({
        ...prev,
        [violationId]: e instanceof Error ? e.message : "Unavailable",
      }));
    } finally {
      setExplaining(null);
    }
  }

  async function compare(version: string) {
    if (!scanId || !version) {
      setDiff(null);
      return;
    }
    try {
      setDiff(await api.ruleDiff(scanId, version));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  }

  if (error) return <ErrorBanner message={error} />;
  if (!scan) return <Loading />;

  const otherVersions = versions.filter((v) => v.version !== scan.rule_version);

  return (
    <>
      <div className="page-head">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h1>{scan.product_name ?? "Unnamed commodity"}</h1>
            <p>
              <Link to="/scans">{t("nav.scans")}</Link> · {formatDateTime(scan.captured_at, lang)} ·{" "}
              {scan.officer_name}
            </p>
          </div>
          <div className="row">
            <VerdictBadge verdict={scan.verdict} />
            <a className="btn btn-primary" href={api.docketUrl(scan.id)} target="_blank" rel="noreferrer">
              {t("scan.docket")}
            </a>
          </div>
        </div>
      </div>

      <div className="split">
        <div className="stack">
          <div className="card">
            <div className="card-head">
              <h2>{t("scan.violations")}</h2>
              <span className="muted">{scan.violations.length}</span>
            </div>
            {scan.not_assessed?.length > 0 && (
              <div style={{ padding: "12px 18px 0" }}>
                <div className="banner banner-warn">
                  <strong>Not assessable from this capture</strong>
                  <ul style={{ margin: "5px 0 0", paddingLeft: 18 }}>
                    {scan.not_assessed.map((item) => (
                      <li key={item.rule_id}>
                        {item.clause} — {item.title}: {item.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {scan.violations.length === 0 ? (
              <div className="empty">{t("scan.noViolations")}</div>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("scan.clause")}</th>
                      <th>{t("scan.finding")}</th>
                      <th>{t("scan.severity")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scan.violations.map((violation) => (
                      <tr
                        key={violation.id}
                        onMouseEnter={() => setHighlight(violation.field)}
                        onMouseLeave={() => setHighlight(null)}
                      >
                        <td>
                          <ClauseTag clause={violation.clause} />
                        </td>
                        <td>
                          <strong>{violation.title}</strong>
                          <div className="muted" style={{ marginTop: 3 }}>
                            {violation.message}
                          </div>
                          {explanations[violation.id] && (
                            <div
                              className="banner banner-info"
                              style={{ marginTop: 8, fontSize: 12.5 }}
                            >
                              {explanations[violation.id]}
                              <div className="muted" style={{ marginTop: 5, fontSize: 11 }}>
                                Advisory explanation — the finding itself comes from the rule engine.
                              </div>
                            </div>
                          )}
                          <button
                            className="btn btn-sm"
                            style={{ marginTop: 8 }}
                            disabled={explaining === violation.id}
                            onClick={() => explain(violation.id)}
                          >
                            {explaining === violation.id ? "…" : t("scan.explain")}
                          </button>
                        </td>
                        <td>
                          <SeverityTag severity={violation.severity} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-head">
              <h2>{t("scan.declarations")}</h2>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("scan.field")}</th>
                    <th>{t("scan.value")}</th>
                    <th>{t("scan.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...scan.declarations]
                    .sort((a, b) => a.field.localeCompare(b.field))
                    .map((declaration) => (
                      <tr
                        key={declaration.id}
                        onMouseEnter={() => setHighlight(declaration.field)}
                        onMouseLeave={() => setHighlight(null)}
                      >
                        <td>{fieldLabel(declaration.field, lang)}</td>
                        <td>{declaration.value ?? <span className="muted">—</span>}</td>
                        <td>
                          <span
                            className={`tag${declaration.status === "missing" ? " tag-high" : ""}`}
                          >
                            {declaration.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="card card-pad">
            <h2 style={{ marginBottom: 10 }}>{t("scan.evidence")}</h2>
            <LabelViewer
              src={api.scanImageUrl(scan.id)}
              declarations={scan.declarations}
              violations={scan.violations}
              highlight={highlight}
            />
            <dl className="dl" style={{ marginTop: 14 }}>
              <dt>{t("scan.imageHash")}</dt>
              <dd className="mono">{scan.image_sha256}</dd>
              <dt>{t("scan.gps")}</dt>
              <dd>
                {scan.gps_lat != null && scan.gps_lon != null ? (
                  <span className="mono">
                    {scan.gps_lat.toFixed(5)}, {scan.gps_lon.toFixed(5)}
                  </span>
                ) : (
                  <span className="muted">not recorded</span>
                )}
              </dd>
              <dt>{t("scan.ledgerEntry")}</dt>
              <dd>
                {scan.ledger_entry ? (
                  <>
                    #{scan.ledger_entry.sequence}{" "}
                    <span className="mono muted">{shortHash(scan.ledger_entry.entry_hash)}</span>
                  </>
                ) : (
                  <span className="muted">not committed</span>
                )}
              </dd>
            </dl>
          </div>

          <div className="card card-pad">
            <h2 style={{ marginBottom: 8 }}>{t("scan.rulePinned")}</h2>
            <p className="muted" style={{ marginTop: 0, fontSize: 12.5 }}>
              This verdict is pinned to rule pack <strong>{scan.rule_version}</strong>, the version
              in force on the inspection date.
            </p>

            {otherVersions.length > 0 && (
              <label className="field" style={{ marginTop: 6 }}>
                {t("scan.compareRules")}
                <select onChange={(e) => compare(e.target.value)} defaultValue="">
                  <option value="">—</option>
                  {otherVersions.map((version) => (
                    <option key={version.version} value={version.version}>
                      {version.version}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {diff && (
              <div
                className={`banner ${diff.verdict_changed ? "banner-warn" : "banner-ok"}`}
                style={{ marginTop: 12 }}
              >
                <strong>
                  {diff.pinned_version} → {diff.target_version}:{" "}
                  {diff.verdict_changed
                    ? `verdict would change to ${diff.target_verdict}`
                    : "verdict unchanged"}
                </strong>
                <div style={{ marginTop: 5, fontSize: 12.5 }}>
                  {diff.rule_changes.length} clause change
                  {diff.rule_changes.length === 1 ? "" : "s"} between these versions. {diff.note}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
