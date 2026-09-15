/**
 * PublicDashboard — P2 anonymized aggregate transparency view.
 *
 * No authentication required. Shows aggregate compliance metrics
 * broken down by district and product category. Zero PII exposed.
 */

import { useEffect, useState } from "react";
import { api } from "../api";
import type { PublicAggregate } from "../types";

function RingGauge({ percent, label }: { percent: number; label: string }) {
  const r = 38;
  const circ = 2 * Math.PI * r;
  const filled = (percent / 100) * circ;
  const hue = Math.round(120 * (percent / 100));

  return (
    <div className="ring-gauge" aria-label={`${label}: ${percent.toFixed(1)}%`}>
      <svg viewBox="0 0 100 100" width="110" height="110">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--color-border)" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke={`hsl(${hue},70%,42%)`}
          strokeWidth="8"
          strokeDasharray={`${filled} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="55" textAnchor="middle" fontSize="16" fontWeight="700" fill="currentColor">
          {percent.toFixed(0)}%
        </text>
      </svg>
      <span className="ring-label">{label}</span>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export default function PublicDashboard() {
  const [data, setData] = useState<PublicAggregate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getPublicAggregate()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="public-dashboard" id="public-dashboard">
      <header className="page-header">
        <div>
          <h1>Compliance Transparency Dashboard</h1>
          <p className="page-subtitle">
            Anonymized aggregate inspection statistics — Legal Metrology enforcement.
          </p>
        </div>
      </header>

      {loading && (
        <div className="loading-ring" aria-live="polite">
          Loading metrics…
        </div>
      )}

      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}

      {data && (
        <>
          <section className="pub-summary-row">
            <MetricCard label="Total Inspections" value={data.total_inspections.toLocaleString()} />
            <MetricCard
              label="Compliant"
              value={data.compliant_count.toLocaleString()}
              sub="Label declared correctly"
            />
            <MetricCard
              label="Non-Compliant"
              value={data.non_compliant_count.toLocaleString()}
              sub="Violations found"
            />
            <MetricCard
              label="Under Review"
              value={data.review_count.toLocaleString()}
              sub="Pending officer review"
            />
            <RingGauge
              percent={data.compliance_rate_percent}
              label="Compliance Rate"
            />
          </section>

          {data.districts.length > 0 && (
            <section className="pub-breakdown-section">
              <h2>By District</h2>
              <div className="pub-table-wrap">
                <table className="pub-table">
                  <thead>
                    <tr>
                      <th>District</th>
                      <th>Inspections</th>
                      <th>Compliant</th>
                      <th>Non-Compliant</th>
                      <th>Under Review</th>
                      <th>Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.districts.map((d) => (
                      <tr key={d.district}>
                        <td>{d.district}</td>
                        <td>{d.total_inspections}</td>
                        <td className="td-go">{d.compliant_count}</td>
                        <td className="td-fail">{d.non_compliant_count}</td>
                        <td className="td-review">{d.review_count}</td>
                        <td>
                          <span
                            className={`compliance-bar-label ${
                              d.compliance_rate_percent >= 80
                                ? "high"
                                : d.compliance_rate_percent >= 50
                                ? "mid"
                                : "low"
                            }`}
                          >
                            {d.compliance_rate_percent.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {data.categories.length > 0 && (
            <section className="pub-breakdown-section">
              <h2>By Product Category</h2>
              <div className="pub-table-wrap">
                <table className="pub-table">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Inspections</th>
                      <th>Compliant</th>
                      <th>Non-Compliant</th>
                      <th>Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.categories.map((c) => (
                      <tr key={c.category}>
                        <td>{c.category}</td>
                        <td>{c.total_inspections}</td>
                        <td className="td-go">{c.compliant_count}</td>
                        <td className="td-fail">{c.non_compliant_count}</td>
                        <td>
                          <span
                            className={`compliance-bar-label ${
                              c.compliance_rate_percent >= 80
                                ? "high"
                                : c.compliance_rate_percent >= 50
                                ? "mid"
                                : "low"
                            }`}
                          >
                            {c.compliance_rate_percent.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <footer className="pub-disclaimer">
            <p>{data.disclaimer}</p>
          </footer>
        </>
      )}
    </div>
  );
}
