import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ErrorBanner, Loading, VerdictBadge, formatDateTime } from "../components/common";
import { useI18n } from "../i18n";
import type { ScanSummary } from "../types";

export default function Scans() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const entityId = params.get("entity") ?? undefined;

  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [verdict, setVerdict] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api
      .listScans({ q: query || undefined, verdict: verdict || undefined, entityId })
      .then(setScans)
      .catch((e) => setError(e.message));
  }, [query, verdict, entityId]);

  if (error) return <ErrorBanner message={error} />;

  return (
    <>
      <div className="page-head">
        <h1>{t("scans.title")}</h1>
        <p>{t("scans.subtitle")}</p>
      </div>

      <div className="card">
        <div className="card-head">
          <input
            type="text"
            value={query}
            placeholder={t("scans.search")}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: 260 }}
          />
          <select value={verdict} onChange={(e) => setVerdict(e.target.value)} style={{ maxWidth: 170 }}>
            <option value="">{t("scans.all")}</option>
            <option value="REVIEW">{t("verdict.REVIEW")}</option>
            <option value="FIX">{t("verdict.FIX")}</option>
            <option value="GO">{t("verdict.GO")}</option>
          </select>
        </div>

        {!scans ? (
          <Loading />
        ) : scans.length === 0 ? (
          <div className="empty">No inspections match.</div>
        ) : (
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
                {scans.map((scan) => (
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
        )}
      </div>
    </>
  );
}
