import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorBanner, Loading, formatDateTime } from "../components/common";
import { IconClock } from "../components/icons";
import { useI18n } from "../i18n";
import type { AuditEntry } from "../types";

/** Who did what, and when — supervisor and above.
 *
 *  Deliberately separate from the evidence ledger: the ledger proves what a record
 *  contains, this proves who acted on it. */
export default function Audit() {
  const { t, lang } = useI18n();
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    api
      .auditLog()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }

  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("audit.title")}</h1>
          <p>{t("audit.subtitle")}</p>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>{t("audit.title")}</h2>
          <span className="muted">{entries?.length ?? ""}</span>
        </div>

        {!entries ? (
          <Loading />
        ) : entries.length === 0 ? (
          <EmptyState icon={<IconClock size={18} />} title={t("audit.empty")} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("audit.when")}</th>
                  <th>{t("audit.actor")}</th>
                  <th>{t("audit.action")}</th>
                  <th>{t("audit.target")}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="muted">{formatDateTime(entry.created_at, lang)}</td>
                    <td>
                      <strong>{entry.actor_username}</strong>
                      <div>
                        <span className="role-pill">
                          {t(`auth.role.${entry.actor_role}` as never)}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="mono">{entry.action}</span>
                      {entry.detail && Object.keys(entry.detail).length > 0 && (
                        <div className="muted" style={{ fontSize: 11.5, marginTop: 3 }}>
                          {Object.entries(entry.detail)
                            .map(([key, value]) => `${key}: ${String(value)}`)
                            .join(" · ")}
                        </div>
                      )}
                    </td>
                    <td>
                      {entry.target_type === "scan" && entry.target_id ? (
                        <Link to={`/inspections/${entry.target_id}`}>
                          {entry.target_id.slice(0, 8)}
                        </Link>
                      ) : entry.target_id ? (
                        <span className="muted">
                          {entry.target_type} {entry.target_id.slice(0, 8)}
                        </span>
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
    </>
  );
}
