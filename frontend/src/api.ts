import type {
  ChainVerification,
  Override,
  LedgerRow,
  Rule,
  RuleDiff,
  RuleVersionSummary,
  Scan,
  ScanSummary,
  Stats,
  WorklistItem,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === "object" && detail !== null && "message" in detail
        ? String((detail as { message: unknown }).message)
        : typeof detail === "string"
          ? detail
          : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail, message);
  }
  return response.json() as Promise<T>;
}

export interface CaptureInput {
  image: File;
  officerName: string;
  lang: string;
  productName?: string;
  gpsLat?: number | null;
  gpsLon?: number | null;
  isFoodItem: boolean;
  isImported: boolean;
  rawText?: string;
  skipQualityGate?: boolean;
}

export const api = {
  health: () =>
    request<{
      status: string;
      active_rule_version: string;
      text_recognition_provider: string;
      nebius_configured: boolean;
      vision_model: string;
    }>("/system/health"),

  createScan: (input: CaptureInput) => {
    const form = new FormData();
    form.append("image", input.image);
    form.append("officer_name", input.officerName);
    form.append("lang", input.lang);
    form.append("is_food_item", String(input.isFoodItem));
    form.append("is_imported", String(input.isImported));
    if (input.productName) form.append("product_name", input.productName);
    if (input.gpsLat != null) form.append("gps_lat", String(input.gpsLat));
    if (input.gpsLon != null) form.append("gps_lon", String(input.gpsLon));
    if (input.rawText) form.append("raw_text", input.rawText);
    if (input.skipQualityGate) form.append("skip_quality_gate", "true");
    return request<{ scan: Scan; quality: unknown }>("/scans", {
      method: "POST",
      body: form,
    });
  },

  listScans: (params: { verdict?: string; q?: string; entityId?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.verdict) search.set("verdict", params.verdict);
    if (params.q) search.set("q", params.q);
    if (params.entityId) search.set("entity_id", params.entityId);
    const suffix = search.toString() ? `?${search}` : "";
    return request<ScanSummary[]>(`/scans${suffix}`);
  },

  getScan: (id: string) => request<Scan>(`/scans/${id}`),

  scanImageUrl: (id: string) => `${BASE}/scans/${id}/image`,

  docketUrl: (id: string) => `${BASE}/scans/${id}/docket`,

  ruleDiff: (id: string, targetVersion: string) =>
    request<RuleDiff>(`/scans/${id}/rule-diff?target_version=${encodeURIComponent(targetVersion)}`),

  explainViolation: (scanId: string, violationId: string, lang: string) =>
    request<{ explanation: string; note: string }>(
      `/scans/${scanId}/violations/${violationId}/explain?lang=${lang}`,
      { method: "POST" },
    ),

  overrideDeclaration: (
    scanId: string,
    body: { declaration_id: string; officer_name: string; new_value: string; reason: string },
  ) =>
    request<Override>(`/scans/${scanId}/overrides`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  listOverrides: (scanId: string) => request<Override[]>(`/scans/${scanId}/overrides`),

  worklist: () => request<WorklistItem[]>("/worklist"),

  stats: () => request<Stats>("/stats"),

  ledger: () => request<LedgerRow[]>("/ledger"),

  verifyLedger: () => request<ChainVerification>("/ledger/verify"),

  ruleVersions: () =>
    request<{ active_version: string; versions: RuleVersionSummary[] }>("/rules"),

  ruleVersion: (version: string) =>
    request<RuleVersionSummary & { rules: Rule[] }>(`/rules/${version}`),
};
