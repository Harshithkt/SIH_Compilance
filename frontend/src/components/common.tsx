import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import type { BBox, Case, CaseStatus, Declaration, Severity, Verdict, Violation } from "../types";
import {
  IconAlertTriangle,
  IconCheckCircle,
  IconHelpCircle,
  IconXCircle,
} from "./icons";

/** The fixed, reserved compliance vocabulary. Every verdict is rendered with both an
 *  icon and a text label — colour never carries the meaning alone. */
const VERDICT_ICON: Record<Verdict, (props: { size?: number }) => ReactNode> = {
  GO: IconCheckCircle,
  FIX: IconAlertTriangle,
  REVIEW: IconXCircle,
  PENDING: IconHelpCircle,
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { t } = useI18n();
  const Icon = VERDICT_ICON[verdict] ?? IconHelpCircle;
  return (
    <span className={`verdict verdict-${verdict}`}>
      <Icon size={13} />
      {t(`verdict.${verdict}` as never)}
    </span>
  );
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  const { t } = useI18n();
  return <span className={`case-badge case-badge-${status}`}>{t(`case.status.${status}` as never)}</span>;
}

export function CaseTrackTag({ track }: { track: Case["track"] }) {
  const { t } = useI18n();
  return <span className="tag">{t(`case.track.${track}` as never)}</span>;
}

/** A due date, rendered in the critical colour once it is past and the case is still
 *  open — the visual cue that a response window has lapsed. */
export function DueDate({ case_ }: { case_: Case }) {
  const { t, lang } = useI18n();
  const overdue = case_.status === "open" && new Date(case_.due_at).getTime() < Date.now();
  return (
    <span className={overdue ? "due-overdue" : undefined}>
      {formatDateTime(case_.due_at, lang)}
      {overdue && ` · ${t("case.overdue")}`}
    </span>
  );
}

export function SeverityTag({ severity }: { severity: string }) {
  return <span className={`tag tag-${severity}`}>{severity.toUpperCase()}</span>;
}

export function ClauseTag({ clause }: { clause: string }) {
  return <span className="tag tag-clause">{clause}</span>;
}

export function Loading({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="empty">
      <span className="spinner" /> <span style={{ marginLeft: 8 }}>{label ?? t("common.loading")}</span>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="banner banner-bad row" style={{ justifyContent: "space-between" }}>
      <span className="row" style={{ gap: 8 }}>
        <IconAlertTriangle size={16} />
        {message}
      </span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

/** A summary tile. `accent` ties a thin left rail + the value's colour to the meaning
 *  of the number (brand = primary count, critical/warning/good = a status count). */
export function Stat({
  value,
  label,
  accent,
}: {
  value: ReactNode;
  label: string;
  accent?: "brand" | "critical" | "warning" | "good";
}) {
  return (
    <div className={`stat${accent ? ` accent-${accent}` : ""}`}>
      {accent && <span className="stat-bar" aria-hidden="true" />}
      <div className={`value${accent ? ` accent-${accent}` : ""}`}>{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}

/** A named, expressive empty state — never a blank card. Always says what happened
 *  and, where there is one, gives the officer something to do about it. */
export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <h3>{title}</h3>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

export function shortHash(hash: string, size = 10) {
  return `${hash.slice(0, size)}…${hash.slice(-4)}`;
}

export function formatDateTime(iso: string, lang: string) {
  return new Date(iso).toLocaleString(lang === "hi" ? "hi-IN" : "en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0].replace(/^Insp\.?$/i, "")[0] ?? parts[0][0];
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || parts[0][0].toUpperCase();
}

/** Capture → Inspect → Review → Complete. Presentational: no step here implies an
 *  async backend state the API doesn't have — "Inspect" covers the moment the photo
 *  is sent for reading, "Review" is the officer looking at what came back (and, on
 *  this page, correcting it), "Complete" is the ledger commit, which happens in the
 *  same transaction as the inspection itself. */
export function Steps({ current }: { current: 0 | 1 | 2 | 3 }) {
  const { t } = useI18n();
  const labels = [t("steps.capture"), t("steps.inspect"), t("steps.review"), t("steps.complete")];
  return (
    <ol className="steps">
      {labels.map((label, index) => (
        <li
          key={label}
          className={index < current ? "done" : index === current ? "active" : undefined}
        >
          <span className="step-num">{index < current ? "✓" : index + 1}</span>
          <span className="step-label">{label}</span>
          {index < labels.length - 1 && <span className="step-connector" />}
        </li>
      ))}
    </ol>
  );
}

export function Timeline({ children }: { children: ReactNode }) {
  return <div className="timeline">{children}</div>;
}

export function TimelineItem({
  children,
  last,
  bad,
}: {
  children: ReactNode;
  last?: boolean;
  bad?: boolean;
}) {
  return (
    <div className="timeline-item">
      <div className="timeline-rail">
        <span className={`timeline-dot${bad ? " bad" : ""}`} />
        {!last && <span className="timeline-line" />}
      </div>
      <div className="timeline-content">{children}</div>
    </div>
  );
}

/** A minimal, reusable confirmation dialog. Used only where a click has a real
 *  evidentiary consequence (e.g. recording a photograph the quality gate rejected) —
 *  not sprinkled in front of routine actions. */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  cancelLabel,
  danger,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="dialog-backdrop" onClick={onCancel}>
      <div className="dialog" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{body}</p>
        <div className="dialog-actions">
          <button className="btn btn-sm" onClick={onCancel}>
            {cancelLabel ?? t("common.cancel")}
          </button>
          <button className={`btn btn-sm ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Maps a declaration/violation severity or presence state onto the fixed status
 *  vocabulary used in `.check-icon` rows. */
export function severityToStatus(severity: Severity): "critical" | "warning" | "pending" {
  if (severity === "high") return "critical";
  if (severity === "medium") return "warning";
  return "pending";
}

interface LabelViewerProps {
  src: string;
  declarations: Declaration[];
  violations: Violation[];
  highlight?: string | null;
}

/** The label photograph with the located declarations drawn on it: green where a
 *  declaration was found, red where the rule engine recorded a contravention. */
export function LabelViewer({ src, declarations, violations, highlight }: LabelViewerProps) {
  const violationFields = new Set(violations.map((v) => v.field));

  const boxes = declarations
    .filter((d): d is Declaration & { bbox: BBox } => Boolean(d.bbox))
    .map((d) => ({
      field: d.field,
      bbox: d.bbox,
      isViolation: violationFields.has(d.field),
    }));

  return (
    <div className="label-viewer">
      <img src={src} alt="Label under inspection" />
      {boxes.map(({ field, bbox, isViolation }) => (
        <div
          key={field}
          className={
            `bbox${isViolation ? "" : " bbox-found"}` +
            (highlight === field ? " bbox-active" : "")
          }
          style={{
            left: `${bbox.x * 100}%`,
            top: `${bbox.y * 100}%`,
            width: `${bbox.w * 100}%`,
            height: `${bbox.h * 100}%`,
            opacity: highlight && highlight !== field ? 0.3 : 1,
          }}
        >
          <span className="bbox-label">{field.replace(/_/g, " ")}</span>
        </div>
      ))}
    </div>
  );
}
