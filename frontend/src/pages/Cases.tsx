import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import {
  CaseStatusBadge,
  CaseTrackTag,
  DueDate,
  EmptyState,
  ErrorBanner,
  Loading,
  formatDateTime,
} from "../components/common";
import { IconFolder } from "../components/icons";
import { useI18n } from "../i18n";
import type { Case } from "../types";

export default function Cases() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const [cases, setCases] = useState<Case[] | null>(null);
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [track, setTrack] = useState(params.get("track") ?? "");
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    api
      .listCases({ status: status || undefined, track: track || undefined })
      .then(setCases)
      .catch((e) => setError(e.message));
  }

  useEffect(load, [status, track]);

  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{t("cases.title")}</h1>
          <p>{t("cases.subtitle")}</p>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: 200 }}>
            <option value="">{t("cases.all")} — {t("cases.filterStatus")}</option>
            <option value="open">{t("case.status.open")}</option>
            <option value="escalated">{t("case.status.escalated")}</option>
            <option value="resolved">{t("case.status.resolved")}</option>
            <option value="unresolved">{t("case.status.unresolved")}</option>
            <option value="rejected">{t("case.status.rejected")}</option>
          </select>
          <select value={track} onChange={(e) => setTrack(e.target.value)} style={{ maxWidth: 200 }}>
            <option value="">{t("cases.all")} — {t("cases.filterTrack")}</option>
            <option value="correction_notice">{t("case.track.correction_notice")}</option>
            <option value="formal_case">{t("case.track.formal_case")}</option>
          </select>
        </div>

        {!cases ? (
          <Loading />
        ) : cases.length === 0 ? (
          <EmptyState icon={<IconFolder size={18} />} title={t("cases.empty")} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("compliance.entity")}</th>
                  <th>{t("case.track.formal_case")}</th>
                  <th>{t("scan.status")}</th>
                  <th>{t("case.owner")}</th>
                  <th>{t("cases.due")}</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id} className="clickable">
                    <td>
                      <Link to={`/inspections/${c.scan_id}`}>
                        <strong>{c.product_name ?? c.scan_id.slice(0, 8)}</strong>
                      </Link>
                      {c.entity_name && (
                        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                          {c.entity_name}
                        </div>
                      )}
                    </td>
                    <td>
                      <CaseTrackTag track={c.track} />
                    </td>
                    <td>
                      <CaseStatusBadge status={c.status} />
                    </td>
                    <td>{c.officer_name}</td>
                    <td>
                      {c.status === "open" || c.status === "escalated" ? (
                        <DueDate case_={c} />
                      ) : (
                        <span className="muted">{formatDateTime(c.closed_at ?? c.due_at, lang)}</span>
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
