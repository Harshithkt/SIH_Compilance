import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import type { BBox, Declaration, Verdict, Violation } from "../types";

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { t } = useI18n();
  return (
    <span className={`verdict verdict-${verdict}`}>{t(`verdict.${verdict}` as never)}</span>
  );
}

export function SeverityTag({ severity }: { severity: string }) {
  return <span className={`tag tag-${severity}`}>{severity.toUpperCase()}</span>;
}

export function ClauseTag({ clause }: { clause: string }) {
  return <span className="tag tag-clause">{clause}</span>;
}

export function Loading() {
  const { t } = useI18n();
  return (
    <div className="empty">
      <span className="spinner" /> <span style={{ marginLeft: 8 }}>{t("common.loading")}</span>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="banner banner-bad row" style={{ justifyContent: "space-between" }}>
      <span>{message}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Stat({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="stat">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
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
