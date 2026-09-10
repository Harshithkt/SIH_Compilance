export type Verdict = "GO" | "FIX" | "REVIEW" | "PENDING";
export type Severity = "high" | "medium" | "low";

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
  confidence: number;
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
  verdict: Verdict;
  not_assessed: { rule_id: string; clause: string; title: string; reason: string }[];
  product_name: string | null;
  is_food_item: boolean;
  is_imported: boolean;
  declarations: Declaration[];
  violations: Violation[];
  ledger_entry: LedgerEntry | null;
}

export interface ScanSummary {
  id: string;
  entity_id: string | null;
  verdict: Verdict;
  product_name: string | null;
  captured_at: string;
  rule_version: string;
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
}

export interface Stats {
  total_scans: number;
  verdicts: Record<string, number>;
  total_violations: number;
  entities_tracked: number;
  top_clauses: { clause: string; count: number }[];
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
