import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ClauseTag, ErrorBanner, Loading, SeverityTag } from "../components/common";
import { fieldLabel, useI18n } from "../i18n";
import type { Rule, RuleVersionSummary } from "../types";

export default function Rules() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const requestedVersion = params.get("version");
  const [versions, setVersions] = useState<RuleVersionSummary[] | null>(null);
  const [activeVersion, setActiveVersion] = useState<string>("");
  const [selected, setSelected] = useState<string>("");
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .ruleVersions()
      .then((response) => {
        setVersions(response.versions);
        setActiveVersion(response.active_version);
        const preselect = response.versions.some((v) => v.version === requestedVersion)
          ? requestedVersion!
          : response.active_version;
        setSelected(preselect);
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selected) return;
    setRules(null);
    api
      .ruleVersion(selected)
      .then((pack) => setRules(pack.rules))
      .catch((e) => setError(e.message));
  }, [selected]);

  if (error) return <ErrorBanner message={error} />;
  if (!versions) return <Loading />;

  const current = versions.find((v) => v.version === selected);

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("rules.title")}</h1>
          <p>{t("rules.subtitle")}</p>
        </div>
      </div>

      <div className="stack">
        <div className="card">
          <div className="card-head">
            <h2>Versions</h2>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Title</th>
                  <th>{t("rules.effective")}</th>
                  <th>{t("rules.count")}</th>
                  <th>SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((version) => (
                  <tr
                    key={version.version}
                    onClick={() => setSelected(version.version)}
                    style={{
                      cursor: "pointer",
                      background: version.version === selected ? "var(--accent-soft)" : undefined,
                    }}
                  >
                    <td>
                      <strong>{version.version}</strong>
                      {version.version === activeVersion && (
                        <span className="tag" style={{ marginLeft: 7 }}>
                          {t("rules.active")}
                        </span>
                      )}
                    </td>
                    <td>{version.title}</td>
                    <td className="muted">{version.effective_date}</td>
                    <td>{version.rule_count}</td>
                    <td className="mono muted">{version.sha256.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>{current?.title ?? selected}</h2>
            <span className="muted mono">{selected}</span>
          </div>
          {!rules ? (
            <Loading />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Clause</th>
                    <th>Requirement</th>
                    <th>Declaration</th>
                    <th>Check</th>
                    <th>Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id}>
                      <td>
                        <ClauseTag clause={rule.clause} />
                      </td>
                      <td>
                        <strong>{rule.title}</strong>
                        <div className="muted" style={{ marginTop: 3 }}>
                          {rule.message}
                        </div>
                        {rule.applies_if && (
                          <div className="muted" style={{ marginTop: 3, fontSize: 12 }}>
                            Applies only when: {fieldLabel(rule.applies_if.field, lang)} ={" "}
                            {String(rule.applies_if.equals)}
                          </div>
                        )}
                        {typeof rule.params?.reference === "string" && (
                          <div className="banner banner-info" style={{ marginTop: 6, fontSize: 11.5 }}>
                            {rule.params.reference}
                          </div>
                        )}
                      </td>
                      <td>{fieldLabel(rule.field, lang)}</td>
                      <td className="mono muted">{rule.check_type}</td>
                      <td>
                        <SeverityTag severity={rule.severity} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
