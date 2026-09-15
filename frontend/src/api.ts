import type { AuthUser } from "./auth";
import type {
  AuditEntry,
  Case,
  ChainVerification,
  EntityDetail,
  MonthlyReport,
  Override,
  LedgerRow,
  OfficerDecisionValue,
  Rule,
  RuleDiff,
  RuleVersionSummary,
  Scan,
  ScanReview,
  ScanSummary,
  Stats,
  WorklistItem,
} from "./types";

const API_ORIGIN = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const BASE = `${API_ORIGIN}/api/v1`;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// Guards against a stalled connection (weak signal, captive portal) leaving fetch
// pending forever — a plain connection refusal already rejects on its own, but a
// request that is sent and never answered would otherwise hang the offline-queue
// sync indefinitely. Kept comfortably above the backend's own Nebius vision timeout
// (90s, see backend/app/config.py) so a slow-but-alive scan is never aborted here —
// that would read as a network failure and re-queue a scan the backend already
// committed, double-posting it to the ledger.
const REQUEST_TIMEOUT_MS = 120_000;

const TOKEN_KEY = "labellens.token";

/** Called when the server rejects our token, so one expired session ends everywhere
 *  rather than only on the screen that happened to make the call. */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* private browsing — the session simply won't survive a reload */
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing stored to remove */
  }
}

/** Fetch a protected file and hand back an object URL.
 *
 *  `<img src>` and `<a href>` are plain browser requests that carry no Authorization
 *  header, so an endpoint behind authentication — the evidence photograph, the docket
 *  — has to be fetched here and passed on as a blob. Callers revoke the URL when they
 *  are done with it. */
export async function fetchObjectUrl(path: string): Promise<string> {
  const token = getToken();
  const response = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (response.status === 401) {
    onUnauthorized?.();
  }
  if (!response.ok) {
    throw new ApiError(response.status, null, `Could not load that file (${response.status}).`);
  }
  return URL.createObjectURL(await response.blob());
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const url = await fetchObjectUrl(path);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      // Spread first so an explicit Content-Type is kept, and never set one here:
      // a FormData body needs the browser to add its own multipart boundary.
      headers: {
        ...(init?.headers as Record<string, string> | undefined),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out. Check your connection and try again.");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
  if (response.status === 401) {
    onUnauthorized?.();
  }
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

  scanImage: (id: string) => fetchObjectUrl(`/scans/${id}/image`),

  downloadDocket: (id: string) =>
    downloadFile(`/scans/${id}/docket`, `LabelLens_Docket_${id.slice(0, 8).toUpperCase()}.pdf`),

  ruleDiff: (id: string, targetVersion: string) =>
    request<RuleDiff>(`/scans/${id}/rule-diff?target_version=${encodeURIComponent(targetVersion)}`),

  explainViolation: (scanId: string, violationId: string, lang: string) =>
    request<{ explanation: string; note: string }>(
      `/scans/${scanId}/violations/${violationId}/explain?lang=${lang}`,
      { method: "POST" },
    ),

  overrideDeclaration: (
    scanId: string,
    body: { declaration_id: string; new_value: string; reason: string },
  ) =>
    request<Override>(`/scans/${scanId}/overrides`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  listOverrides: (scanId: string) => request<Override[]>(`/scans/${scanId}/overrides`),

  submitReview: (
    scanId: string,
    body: { decision: OfficerDecisionValue; notes?: string },
  ) =>
    request<Scan>(`/scans/${scanId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  listReviews: (scanId: string) => request<ScanReview[]>(`/scans/${scanId}/reviews`),

  listCases: (params: { status?: string; track?: string; entityId?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.track) search.set("track", params.track);
    if (params.entityId) search.set("entity_id", params.entityId);
    const suffix = search.toString() ? `?${search}` : "";
    return request<Case[]>(`/cases${suffix}`);
  },

  getCase: (caseId: string) => request<Case>(`/cases/${caseId}`),

  closeCase: (
    caseId: string,
    body: { resolution: "resolved" | "unresolved"; notes?: string },
  ) =>
    request<Case>(`/cases/${caseId}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  listUsers: () => request<AuthUser[]>("/auth/users"),

  createUser: (body: {
    username: string;
    full_name: string;
    password: string;
    role: string;
  }) =>
    request<AuthUser>("/auth/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  setUserActive: (username: string, active: boolean) =>
    request<AuthUser>(
      `/auth/users/${encodeURIComponent(username)}/active?active=${active}`,
      { method: "POST" },
    ),

  auditLog: (limit = 100) => request<AuditEntry[]>(`/auth/audit?limit=${limit}`),

  worklist: () => request<WorklistItem[]>("/worklist"),

  entity: (id: string) => request<EntityDetail>(`/entities/${id}`),

  stats: () => request<Stats>("/stats"),

  monthlyReport: (year: number, month: number) =>
    request<MonthlyReport>(`/reports/monthly?year=${year}&month=${month}`),

  downloadMonthlyReport: (year: number, month: number) =>
    downloadFile(
      `/reports/monthly?year=${year}&month=${month}`,
      `LabelLens_Report_${year}-${String(month).padStart(2, "0")}.json`,
    ),

  ledger: () => request<LedgerRow[]>("/ledger"),

  verifyLedger: () => request<ChainVerification>("/ledger/verify"),

  ruleVersions: () =>
    request<{ active_version: string; versions: RuleVersionSummary[] }>("/rules"),

  ruleVersion: (version: string) =>
    request<RuleVersionSummary & { rules: Rule[] }>(`/rules/${version}`),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<unknown>("/auth/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
};
