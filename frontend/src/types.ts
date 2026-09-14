export type Verdict = "GO" | "FIX" | "REVIEW" | "PENDING";
export type Severity = "high" | "medium" | "low";
export type OfficerDecisionValue = "confirmed" | "rejected" | "needs_more_evidence";
export type CaseTrack = "correction_notice" | "formal_case";
export type CaseStatus = "open" | "escalated" | "resolved" | "unresolved" | "rejected";

export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Declaration {
  id: string;
  field: string;
  value: string | null;
  present: boolean;
  status: string;
  confidence: number | null;
  ocr_confidence?: number | null;
  extraction_confidence?: number | null;
  original_ocr_text?: string | null;
  bbox: BBox | null;
  height_px: number | null;
}

export interface Violation {
  id: string;
  rule_id: string;
  clause: string;
  title: string;
  field: string;
  severity: Severity;
  message: string;
  bbox: BBox | null;
}

export interface LedgerEntry {
  sequence: number;
  prev_hash: string;
  payload_hash: string;
  entry_hash: string;
  created_at: string;
}

export interface Case {
  id: string;
  scan_id: string;
  entity_id: string | null;
  entity_name: string | null;
  product_name: string | null;
  track: CaseTrack;
  severity: Severity;
  status: CaseStatus;
  officer_name: string;
  rule_version: string;
  opened_at: string;
  due_at: string;
  response_days: number;
  is_overdue: boolean;
  escalated_at: string | null;
  escalated_to: string | null;
  closed_at: string | null;
  closed_by: string | null;
  resolution_notes: string | null;
  evidence_hash_at_close: string | null;
  countersigned_by: string | null;
}

export interface ScanReview {
  id: string;
  scan_id: string;
  officer_name: string;
  decision: OfficerDecisionValue;
  notes: string | null;
  created_at: string;
}

export interface EntityRole {
  id: string;
  scan_id: string;
  role: string;
  entity_name: string | null;
  address_text: string | null;
  raw_value: string | null;
  ocr_confidence: number | null;
  extraction_confidence: number | null;
  extraction_status: string;
  original_ocr_text: string | null;
  bbox: BBox | null;
  height_px: number | null;
  created_at: string;
}

export interface Scan {
  id: string;
  entity_id: string | null;
  officer_name: string;
  image_sha256: string;
  gps_lat: number | null;
  gps_lon: number | null;
  captured_at: string;
  rule_version: string;
  ocr_lang: string;
  ocr_provider: string;
  ocr_mode?: "online" | "offline" | string;
  ocr_fallback_from?: string | null;
  ocr_fallback_reason?: string | null;
  verdict: Verdict;
  not_assessed: { rule_id: string; clause: string; title: string; reason: string }[];
  product_name: string | null;
  is_food_item: boolean;
  is_imported: boolean;
  officer_decision: OfficerDecisionValue | null;
  officer_decision_by: string | null;
  officer_decision_at: string | null;
  officer_decision_notes: string | null;
  declarations: Declaration[];
  violations: Violation[];
  entity_roles?: EntityRole[];
  ledger_entry: LedgerEntry | null;
  case: Case | null;
}

export interface ScanSummary {
  id: string;
  entity_id: string | null;
  verdict: Verdict;
  product_name: string | null;
  captured_at: string;
  rule_version: string;
  officer_decision: OfficerDecisionValue | null;
}

export interface QualityReport {
  passed: boolean;
  metrics: Record<string, number>;
  issues: { code: string; message: string; guidance: string }[];
}

export interface WorklistItem {
  entity: {
    id: string;
    name: string;
    address: string | null;
    license_no: string | null;
    fssai_no: string | null;
  };
  scan_count: number;
  violation_count: number;
  high_severity_count: number;
  risk_score: number;
  repeat_offender: boolean;
  latest_verdict: Verdict | null;
  latest_scan_at: string | null;
  top_clauses: { clause: string; count: number }[];
  pending_response_count: number;
}

export interface Stats {
  total_scans: number;
  verdicts: Record<string, number>;
  total_violations: number;
  entities_tracked: number;
  top_clauses: { clause: string; count: number }[];
  pending_review: number;
  cases: Record<CaseStatus, number>;
}

export interface LedgerRow extends LedgerEntry {
  scan_id: string;
  verdict: Verdict | null;
  officer_name: string | null;
}

export interface ChainVerification {
  valid: boolean;
  checked_entries: number;
  broken_at_sequence: number | null;
  detail: string;
}

export interface RuleVersionSummary {
  version: string;
  title: string;
  effective_date: string;
  superseded_by: string | null;
  rule_count: number;
  sha256: string;
}

export interface Rule {
  id: string;
  clause: string;
  title: string;
  field: string;
  check_type: string;
  severity: Severity;
  message: string;
  params?: Record<string, unknown>;
  applies_if?: { field: string; equals: boolean };
}

export interface RuleDiff {
  scan_id: string;
  pinned_version: string;
  pinned_verdict: Verdict;
  target_version: string;
  target_verdict: Verdict;
  verdict_changed: boolean;
  rule_changes: { rule_id: string; change: string }[];
  target_violations: Violation[];
  note: string;
}

export interface Override {
  id: string;
  declaration_id: string;
  officer_name: string;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  created_at: string;
}

export interface EntityDetail {
  entity: WorklistItem["entity"];
  risk_score: number;
  repeat_offender: boolean;
  scan_count: number;
  violation_count: number;
  high_severity_count: number;
  pending_response_count: number;
  top_clauses: { clause: string; count: number }[];
  scans: ScanSummary[];
}

export interface MonthlyReport {
  period: { year: number; month: number; label: string; from: string; to: string };
  totals: {
    inspections: number;
    non_compliant: number;
    non_compliance_rate: number;
    findings: number;
    entities_with_findings: number;
    pending_response: number;
  };
  verdicts: Record<string, number>;
  rule_versions_applied: Record<string, number>;
  inspections_by_officer: { officer: string; inspections: number }[];
  clause_breakdown: { clause: string; title: string; count: number }[];
  priority_entities: {
    name: string;
    address: string | null;
    risk_score: number;
    findings_in_period: number;
    repeat_offender: boolean;
  }[];
  evidence_integrity: ChainVerification;
  generated_at: string;
  note: string;
}
