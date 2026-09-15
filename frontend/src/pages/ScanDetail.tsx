import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import {
  CaseStatusBadge,
  CaseTrackTag,
  ClauseTag,
  DueDate,
  ErrorBanner,
  LabelViewer,
  Loading,
  Steps,
  VerdictBadge,
  formatDateTime,
  shortHash,
} from "../components/common";
import {
  IconAlertTriangle,
  IconArrowRight,
  IconCheckCircle,
  IconHelpCircle,
  IconXCircle,
  IconZoomIn,
  IconZoomOut,
} from "../components/icons";
import { fieldLabel, useI18n } from "../i18n";
import type {
  Declaration,
  OfficerDecisionValue,
  Override,
  Rule,
  RuleDiff,
  RuleVersionSummary,
  Scan,
} from "../types";

type CheckStatus = "good" | "warning" | "critical" | "pending";

interface CheckRow {
  rule: Rule;
  status: CheckStatus;
  detail: string;
  violationId?: string;
}

/** Reconstructs the full pass/fail/unable-to-verify list for this scan's pinned rule
 *  pack — the API only returns contraventions and not-assessed items (a passing check
 *  is not "news"), so a compliant row is anything left over once those two are
 *  accounted for, minus rules this package is exempt from. */
function buildChecks(rules: Rule[], scan: Scan): CheckRow[] {
  const declByField = new Map(scan.declarations.map((d) => [d.field, d]));
  const violationByRule = new Map(scan.violations.map((v) => [v.rule_id, v]));
  const notAssessedByRule = new Map(scan.not_assessed.map((n) => [n.rule_id, n]));

  const rows: CheckRow[] = [];
  for (const rule of rules) {
    if (rule.applies_if) {
      const context =
        rule.applies_if.field === "is_imported"
          ? scan.is_imported
          : rule.applies_if.field === "is_food_item"
            ? scan.is_food_item
            : undefined;
      if (context !== rule.applies_if.equals) continue;
    }

    const decl = declByField.get(rule.field);
    // A type-size check never ran at all when the declaration itself is missing —
    // that is already the presence rule's finding, not a second one.
    if (rule.check_type === "min_height_ratio" && !(decl && decl.present)) continue;

    const violation = violationByRule.get(rule.id);
    if (violation) {
      rows.push({
        rule,
        status: violation.severity === "high" ? "critical" : "warning",
        detail: violation.message,
        violationId: violation.id,
      });
      continue;
    }

    const notAssessed = notAssessedByRule.get(rule.id);
    if (notAssessed) {
      rows.push({ rule, status: "pending", detail: notAssessed.reason });
      continue;
    }

    rows.push({ rule, status: "good", detail: decl?.value || "Requirement satisfied." });
  }
  return rows;
}

const CHECK_ICON: Record<CheckStatus, (props: { size?: number }) => ReactNode> = {
  good: IconCheckCircle,
  critical: IconXCircle,
  warning: IconAlertTriangle,
  pending: IconHelpCircle,
};

export default function ScanDetail() {
  const { scanId } = useParams<{ scanId: string }>();
  const { t, lang } = useI18n();

  const [scan, setScan] = useState<Scan | null>(null);
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [versions, setVersions] = useState<RuleVersionSummary[]>([]);
  const [diff, setDiff] = useState<RuleDiff | null>(null);
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [explaining, setExplaining] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Override[]>([]);
  const [editing, setEditing] = useState<Declaration | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editReason, setEditReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<OfficerDecisionValue | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [closingCase, setClosingCase] = useState<"resolved" | "unresolved" | null>(null);
  const [closeNotes, setCloseNotes] = useState("");
  const [closing, setClosing] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  function load() {
    if (!scanId) return;
    setError(null);
    api
      .getScan(scanId)
      .then((s) => {
        setScan(s);
        return api.ruleVersion(s.rule_version);
      })
      .then((pack) => setRules(pack.rules))
      .catch((e) => setError(e.message));
    api.listOverrides(scanId).then(setOverrides).catch(() => setOverrides([]));
  }

  useEffect(() => {
    load();
    api
      .ruleVersions()
      .then((r) => setVersions(r.versions))
      .catch(() => setVersions([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanId]);

  // The evidence photograph sits behind authentication, so it is fetched with the
  // session token and handed to the viewer as an object URL — the browser would send
  // no Authorization header if it loaded the API path itself.
  useEffect(() => {
    if (!scanId) return;
    let objectUrl: string | null = null;
    api
      .scanImage(scanId)
      .then((url) => {
        objectUrl = url;
        setImageUrl(url);
      })
      .catch(() => setImageUrl(null));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [scanId]);

  function startEdit(declaration: Declaration) {
    setEditing(declaration);
    setEditValue(declaration.value ?? "");
    setEditReason("");
  }

  async function saveOverride() {
    if (!scanId || !editing || !editReason.trim()) return;
    setSaving(true);
    try {
      await api.overrideDeclaration(scanId, {
        declaration_id: editing.id,
        new_value: editValue,
        reason: editReason.trim(),
      });
      setEditing(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  async function submitReview() {
    if (!scanId || !pendingDecision) return;
    if (pendingDecision !== "confirmed" && !reviewNotes.trim()) return;
    setReviewing(true);
    try {
      await api.submitReview(scanId, {
        decision: pendingDecision,
        notes: reviewNotes.trim() || undefined,
      });
      setPendingDecision(null);
      setReviewNotes("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setReviewing(false);
    }
  }

  async function submitCloseCase() {
    if (!scan?.case || !closingCase) return;
    setClosing(true);
    try {
      await api.closeCase(scan.case.id, {
        resolution: closingCase,
        notes: closeNotes.trim() || undefined,
      });
      setClosingCase(null);
      setCloseNotes("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setClosing(false);
    }
  }

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

  const checks = useMemo(() => (scan && rules ? buildChecks(rules, scan) : []), [scan, rules]);

  if (error) return <ErrorBanner message={error} />;
  if (!scan) return <Loading />;

  const otherVersions = versions.filter((v) => v.version !== scan.rule_version);

  return (
    <>
      <p className="crumb">
        <Link to="/inspections">{t("nav.inspections")}</Link>
      </p>
      <div className="page-head">
        <div className="page-head-text">
          <h1>{scan.product_name ?? "Unnamed commodity"}</h1>
          <p>
            {formatDateTime(scan.captured_at, lang)} · {scan.officer_name}
          </p>
          <div className="row" style={{ gap: 6, marginTop: 4, alignItems: "center" }}>
            <span className="tag" style={{ fontSize: 11, textTransform: "uppercase" }}>
              {scan.ocr_provider} · {scan.ocr_mode ?? "online"}
            </span>
            {scan.ocr_fallback_from && (
              <span className="tag tag-medium" style={{ fontSize: 11 }}>
                Fell back from {scan.ocr_fallback_from} ({scan.ocr_fallback_reason ?? "fallback"})
              </span>
            )}
          </div>
        </div>
        <div className="page-head-actions">
          <VerdictBadge verdict={scan.verdict} />
          <button
            className="btn btn-primary"
            onClick={() =>
              api
                .downloadDocket(scan.id)
                .catch((e) => setError(e instanceof Error ? e.message : t("common.error")))
            }
          >
            {t("scan.docket")}
          </button>
        </div>
      </div>

      <Steps current={scan.verdict === "GO" || scan.officer_decision ? 3 : 2} />
      <div
        className={`banner ${scan.ledger_entry ? "banner-ok" : "banner-warn"}`}
        style={{ marginBottom: 20, display: "inline-flex" }}
      >
        {scan.ledger_entry ? (
          <>
            {t("scan.committed")} — #{scan.ledger_entry.sequence}{" "}
            <span className="mono" style={{ marginLeft: 6 }}>
              {shortHash(scan.ledger_entry.entry_hash, 8)}
            </span>
          </>
        ) : (
          t("scan.notCommitted")
        )}
      </div>

      <div className="split">
        <div className="stack">
          <div className="card card-pad">
            <div className="evidence-toolbar">
              <h2>{t("scan.evidence")}</h2>
              <div className="row" style={{ gap: 4 }}>
                <button
                  className="btn btn-sm btn-icon"
                  onClick={() => setZoom((z) => Math.max(1, z - 0.5))}
                  disabled={zoom <= 1}
                  aria-label="Zoom out"
                >
                  <IconZoomOut size={15} />
                </button>
                <button
                  className="btn btn-sm btn-icon"
                  onClick={() => setZoom((z) => Math.min(3, z + 0.5))}
                  disabled={zoom >= 3}
                  aria-label="Zoom in"
                >
                  <IconZoomIn size={15} />
                </button>
              </div>
            </div>
            <div className="evidence-frame" style={{ overflow: "auto", maxHeight: 560 }}>
              <div
                style={{
                  transform: `scale(${zoom})`,
                  transformOrigin: "0 0",
                  width: zoom > 1 ? `${zoom * 100}%` : undefined,
                }}
              >
                {imageUrl ? (
                  <LabelViewer
                    src={imageUrl}
                    declarations={scan.declarations}
                    violations={scan.violations}
                    highlight={highlight}
                  />
                ) : (
                  <Loading />
                )}
              </div>
            </div>
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
              <dt>OCR Engine</dt>
              <dd>
                <span className="mono">{scan.ocr_provider}</span> · {scan.ocr_mode ? scan.ocr_mode.toUpperCase() : "ONLINE"} ({scan.ocr_lang})
                {scan.ocr_fallback_from && (
                  <div style={{ fontSize: 11, marginTop: 2, color: "var(--status-warning)" }}>
                    Fell back from {scan.ocr_fallback_from} ({scan.ocr_fallback_reason ?? "fallback"})
                  </div>
                )}
              </dd>
            </dl>
          </div>

          <div className="card card-pad">
            <h2 style={{ marginBottom: 8 }}>{t("scan.rulePinned")}</h2>
            <p className="muted" style={{ marginTop: 0, fontSize: 12.5 }}>
              This verdict is pinned to rule pack{" "}
              <Link to={`/rules?version=${encodeURIComponent(scan.rule_version)}`}>
                <strong>{scan.rule_version}</strong>
              </Link>
              , the version in force on the inspection date.
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

        <div className="stack">
          <div className="card">
            <div className="card-head">
              <div className="card-head-text">
                <h2>{t("scan.violations")}</h2>
                <p>Every applicable provision in this rule pack, checked against what was read.</p>
              </div>
              <span className="muted">{checks.length}</span>
            </div>
            {checks.length === 0 ? (
              <div className="empty">{t("scan.noViolations")}</div>
            ) : (
              <div>
                {checks.map((row) => {
                  const Icon = CHECK_ICON[row.status];
                  return (
                    <div className="check" key={row.rule.id}>
                      <span className={`check-icon ${row.status}`}>
                        <Icon size={13} />
                      </span>
                      <div className="check-body">
                        <div className="check-title-row">
                          <span className="check-title">{row.rule.title}</span>
                          <ClauseTag clause={row.rule.clause} />
                        </div>
                        <div className="check-detail">{row.detail}</div>
                        {row.violationId && explanations[row.violationId] && (
                          <div className="banner banner-info" style={{ marginTop: 8, fontSize: 12.5 }}>
                            {explanations[row.violationId]}
                            <div className="muted" style={{ marginTop: 5, fontSize: 11 }}>
                              Advisory explanation — the finding itself comes from the rule engine.
                            </div>
                          </div>
                        )}
                        {row.violationId && (
                          <button
                            className="btn btn-sm"
                            style={{ marginTop: 8 }}
                            disabled={explaining === row.violationId}
                            onClick={() => explain(row.violationId!)}
                          >
                            {explaining === row.violationId ? "…" : t("scan.explain")}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-head">
              <div className="card-head-text">
                <h2>{t("scan.declarations")}</h2>
                <p>{t("scan.declarationsHelp")}</p>
              </div>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("scan.field")}</th>
                    <th>{t("scan.value")}</th>
                    <th>OCR Conf.</th>
                    <th>{t("scan.status")}</th>
                    <th />
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
                        <td>
                          {editing?.id === declaration.id ? (
                            <div className="stack" style={{ gap: 7 }}>
                              <input
                                type="text"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                placeholder="Value as printed on the pack"
                                autoFocus
                              />
                              <input
                                type="text"
                                value={editReason}
                                onChange={(e) => setEditReason(e.target.value)}
                                placeholder="Reason for the correction (required)"
                              />
                              <div className="row">
                                <button
                                  className="btn btn-sm btn-primary"
                                  onClick={saveOverride}
                                  disabled={saving || !editReason.trim()}
                                >
                                  {saving ? "Saving…" : "Save correction"}
                                </button>
                                <button className="btn btn-sm" onClick={() => setEditing(null)}>
                                  {t("common.close")}
                                </button>
                              </div>
                            </div>
                          ) : (
                            (declaration.value ?? <span className="muted">—</span>)
                          )}
                        </td>
                        <td>
                          {declaration.ocr_confidence != null ? (
                            <span className="mono" title={`OCR confidence: ${(declaration.ocr_confidence * 100).toFixed(1)}%`}>
                              {(declaration.ocr_confidence * 100).toFixed(0)}%
                            </span>
                          ) : declaration.confidence != null ? (
                            <span className="mono" title={`Confidence: ${(declaration.confidence * 100).toFixed(1)}%`}>
                              {(declaration.confidence * 100).toFixed(0)}%
                            </span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td>
                          <DeclarationStatus declaration={declaration} />
                        </td>
                        <td>
                          {editing?.id !== declaration.id && (
                            <div className="stack" style={{ gap: 5 }}>
                              {declaration.bbox ? (
                                <button
                                  className="locate-btn"
                                  onClick={() => setHighlight(declaration.field)}
                                >
                                  {t("scan.locate")} <IconArrowRight size={11} />
                                </button>
                              ) : declaration.present ? (
                                <span className="muted" style={{ fontSize: 11 }}>
                                  Text detected — location evidence unavailable
                                </span>
                              ) : null}
                              <button className="btn btn-sm" onClick={() => startEdit(declaration)}>
                                {t("scan.correct")}
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {(scan.entity_roles || []).length > 0 && (
            <div className="card">
              <div className="card-head">
                <div className="card-head-text">
                  <h2>Entity Roles</h2>
                  <p>Manufacturer, Packer, and Importer entity declarations with role evidence.</p>
                </div>
                <span className="muted">{(scan.entity_roles || []).length}</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Role</th>
                      <th>Entity Name</th>
                      <th>Address</th>
                      <th>Signal</th>
                      <th>OCR Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(scan.entity_roles || []).map((er) => (
                      <tr key={er.id}>
                        <td>
                          <strong style={{ textTransform: "capitalize" }}>{er.role}</strong>
                        </td>
                        <td>{er.entity_name || <span className="muted">—</span>}</td>
                        <td>{er.address_text || <span className="muted">—</span>}</td>
                        <td>
                          <span
                            className={`badge ${
                              er.extraction_status === "found"
                                ? "badge-good"
                                : er.extraction_status === "partial"
                                  ? "badge-warn"
                                  : "badge-muted"
                            }`}
                          >
                            {er.extraction_status}
                          </span>
                        </td>
                        <td>
                          {er.ocr_confidence != null ? (
                            <span className="mono">{(er.ocr_confidence * 100).toFixed(0)}%</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card card-pad">
            <h2 style={{ marginBottom: 6 }}>{t("review.title")}</h2>
            <p className="muted" style={{ marginTop: 0, fontSize: 12.5 }}>
              {t("review.help")}
            </p>

            {scan.officer_decision && !pendingDecision ? (
              <div className="banner banner-info stack" style={{ gap: 4, marginTop: 10 }}>
                <strong>
                  {t(`review.decision.${scan.officer_decision}` as never)} — {scan.officer_decision_by}
                </strong>
                <span style={{ fontSize: 12 }}>
                  {scan.officer_decision_at && formatDateTime(scan.officer_decision_at, lang)}
                </span>
                {scan.officer_decision_notes && <span>{scan.officer_decision_notes}</span>}
                <button
                  className="btn btn-sm"
                  style={{ alignSelf: "flex-start", marginTop: 4 }}
                  onClick={() => setPendingDecision("confirmed")}
                >
                  {t("review.reReview")}
                </button>
              </div>
            ) : pendingDecision ? (
              <div className="stack" style={{ gap: 8, marginTop: 10 }}>
                <div className="row">
                  {(["confirmed", "rejected", "needs_more_evidence"] as OfficerDecisionValue[]).map((d) => (
                    <button
                      key={d}
                      className={`btn btn-sm${pendingDecision === d ? " btn-primary" : ""}`}
                      onClick={() => setPendingDecision(d)}
                    >
                      {t(`review.decision.${d}` as never)}
                    </button>
                  ))}
                </div>
                <textarea
                  rows={2}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder={
                    pendingDecision === "confirmed" ? t("review.notes") : t("review.notesPlaceholder")
                  }
                />
                <div className="row">
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={submitReview}
                    disabled={reviewing || (pendingDecision !== "confirmed" && !reviewNotes.trim())}
                  >
                    {reviewing ? "…" : t("review.submit")}
                  </button>
                  <button className="btn btn-sm" onClick={() => setPendingDecision(null)}>
                    {t("common.cancel")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn btn-sm btn-primary" onClick={() => setPendingDecision("confirmed")}>
                  {t("review.confirm")}
                </button>
                <button className="btn btn-sm" onClick={() => setPendingDecision("rejected")}>
                  {t("review.reject")}
                </button>
                <button className="btn btn-sm" onClick={() => setPendingDecision("needs_more_evidence")}>
                  {t("review.needsEvidence")}
                </button>
              </div>
            )}
          </div>

          {scan.case && (
            <div className="card card-pad">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
                <h2>{t("case.title")}</h2>
                <div className="row" style={{ gap: 6 }}>
                  <CaseTrackTag track={scan.case.track} />
                  <CaseStatusBadge status={scan.case.status} />
                </div>
              </div>
              <dl className="dl">
                <dt>{t("case.owner")}</dt>
                <dd>{scan.case.officer_name}</dd>
                <dt>{t("case.opened")}</dt>
                <dd>{formatDateTime(scan.case.opened_at, lang)}</dd>
                <dt>{t("case.due")}</dt>
                <dd>
                  <DueDate case_={scan.case} />
                </dd>
                {scan.case.status === "escalated" && (
                  <>
                    <dt>{t("case.escalatedTo")}</dt>
                    <dd>{scan.case.escalated_to}</dd>
                  </>
                )}
                {scan.case.closed_at && (
                  <>
                    <dt>{t("case.closedBy")}</dt>
                    <dd>
                      {scan.case.closed_by} · {formatDateTime(scan.case.closed_at, lang)}
                    </dd>
                  </>
                )}
                {scan.case.countersigned_by && (
                  <>
                    <dt>{t("case.countersignedBy")}</dt>
                    <dd>{scan.case.countersigned_by}</dd>
                  </>
                )}
                {scan.case.resolution_notes && (
                  <>
                    <dt>{t("case.resolutionNotes")}</dt>
                    <dd>{scan.case.resolution_notes}</dd>
                  </>
                )}
              </dl>

              {(scan.case.status === "open" || scan.case.status === "escalated") &&
                (closingCase ? (
                  <div className="stack" style={{ gap: 8, marginTop: 10 }}>
                    <textarea
                      rows={2}
                      value={closeNotes}
                      onChange={(e) => setCloseNotes(e.target.value)}
                      placeholder={t("case.closeNotes")}
                    />
                    <div className="row">
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={submitCloseCase}
                        disabled={closing}
                      >
                        {closing ? "…" : t("common.confirm")}
                      </button>
                      <button className="btn btn-sm" onClick={() => setClosingCase(null)}>
                        {t("common.cancel")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="row" style={{ marginTop: 10 }}>
                    <button className="btn btn-sm btn-primary" onClick={() => setClosingCase("resolved")}>
                      {t("case.closeResolved")}
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => setClosingCase("unresolved")}>
                      {t("case.closeUnresolved")}
                    </button>
                  </div>
                ))}
            </div>
          )}

          <div className="card card-pad">
            <h2 style={{ marginBottom: 6 }}>{t("scan.auditTrail")}</h2>
            {overrides.length === 0 ? (
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
                No corrections have been made to this inspection.
              </p>
            ) : (
              <div className="table-scroll" style={{ marginTop: 4 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Officer</th>
                      <th>Change</th>
                      <th>Reason</th>
                      <th>Recorded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overrides.map((override) => (
                      <tr key={override.id}>
                        <td>{override.officer_name}</td>
                        <td>
                          <span className="muted">{override.old_value ?? "—"}</span> →{" "}
                          <strong>{override.new_value}</strong>
                        </td>
                        <td>{override.reason}</td>
                        <td className="muted">{formatDateTime(override.created_at, lang)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function DeclarationStatus({ declaration }: { declaration: Declaration }) {
  const { t } = useI18n();
  const status = declaration.status;
  const map: Record<string, { icon: (p: { size?: number }) => ReactNode; cls: CheckStatus; label: string }> = {
    missing: { icon: IconXCircle, cls: "critical", label: t("scan.statusMissing") },
    officer_verified: { icon: IconCheckCircle, cls: "good", label: t("scan.statusOfficerVerified") },
    illegible: { icon: IconHelpCircle, cls: "pending", label: t("scan.statusIllegible") },
    verified: { icon: IconCheckCircle, cls: "good", label: t("scan.statusVerified") },
  };
  const entry = map[status] ?? map.verified;
  const Icon = entry.icon;
  const rawConf = declaration.ocr_confidence ?? declaration.confidence;
  const confidencePct =
    declaration.present && rawConf != null && rawConf > 0 ? Math.round(rawConf * 100) : null;

  return (
    <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
      <span className={`check-icon ${entry.cls}`} style={{ width: 17, height: 17 }}>
        <Icon size={10} />
      </span>
      <span style={{ fontSize: 12.5 }}>
        {entry.label}
        {confidencePct !== null && (
          <span className="muted" style={{ marginLeft: 5 }}>
            · {confidencePct}% {t("scan.confidence").toLowerCase()}
          </span>
        )}
      </span>
    </span>
  );
}
