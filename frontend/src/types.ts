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
  source_type?: "PHYSICAL_LABEL" | "ECOMMERCE_LISTING";
  inspection_visit_id?: string | null;
  officer_decision: OfficerDecisionValue | null;
  officer_decision_by: string | null;
  officer_decision_at: string | null;
  officer_decision_notes: string | null;
  declarations: Declaration[];
  violations: Violation[];
  entity_roles?: EntityRole[];
  ledger_entry: LedgerEntry | null;
  case: Case | null;
  physical_verifications?: PhysicalVerification[];
}

export interface ScanSummary {
  id: string;
  entity_id: string | null;
  officer_name: string;
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

/** One entry from the append-only record of identity-sensitive actions. Separate
 *  from the evidence ledger: that proves what a record contains, this proves who
 *  did something to it. */
export interface AuditEntry {
  id: string;
  actor_username: string;
  actor_role: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
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

// -------------------------------------------------------
// P0 Physical Verification
// -------------------------------------------------------
export type PhysicalVerificationResult = "PASS" | "FAIL" | "REVIEW" | "NOT_ASSESSABLE";

export interface PhysicalVerification {
  id: string;
  scan_id: string;
  case_id: string | null;
  entity_id: string | null;
  sample_number: number;
  declared_quantity: string;
  declared_unit: string;
  observed_quantity: number;
  observed_unit: string;
  normalized_declared_quantity: number;
  normalized_observed_quantity: number;
  shortfall: number;
  applicable_rule_id: string;
  applicable_rule_version: string;
  applicable_mpe: number;
  tolerance_basis: "percentage" | "absolute";
  result: PhysicalVerificationResult;
  verification_status: "CONFIRMED" | "DRAFT";
  officer_username: string;
  timestamp: string;
  notes: string | null;
  calculation_details: Record<string, unknown> | null;
  evidence_hash: string | null;
}

export interface PhysicalVerificationCreate {
  scan_id: string;
  case_id?: string;
  sample_number?: number;
  declared_quantity: string;
  declared_unit: string;
  observed_quantity: number;
  observed_unit: string;
  notes?: string;
}

// -------------------------------------------------------
// P1 Price Anomaly Signal
// -------------------------------------------------------
export type PriceAnomalySignal = "NO_SIGNAL" | "LOW_SIGNAL" | "REVIEW" | "INSUFFICIENT_HISTORY";

export interface PriceAnomaly {
  scan_id: string;
  product_name: string | null;
  category: string | null;
  price: number | null;
  declared_quantity: string | null;
  unit_price: number | null;
  historical_avg_unit_price: number | null;
  historical_sample_count: number;
  signal: PriceAnomalySignal;
  explanation: string;
  disclaimer: string;
}

// -------------------------------------------------------
// P2 Contact Validation
// -------------------------------------------------------
export type ValidationStatus = "PASS" | "FAIL" | "NOT_ASSESSABLE";

export interface ContactValidation {
  scan_id: string;
  phone: string | null;
  phone_status: ValidationStatus;
  phone_message: string | null;
  email: string | null;
  email_status: ValidationStatus;
  email_message: string | null;
  disclaimer: string;
}

// -------------------------------------------------------
// P2 Multi-Unit Consistency
// -------------------------------------------------------
export type ConsistencyStatus = "CONSISTENT" | "INCONSISTENT" | "INSUFFICIENT_EVIDENCE";

export interface MultiUnitConsistency {
  inspection_visit_id: string;
  unit_count: number;
  status: ConsistencyStatus;
  differing_declarations: Array<{
    field: string;
    detected_values: string[];
    breakdown: Record<string, string>;
    message: string;
  }>;
  explanation: string;
}

// -------------------------------------------------------
// P2 Historical Enforcement Signal
// -------------------------------------------------------
export type HistorySignalLevel =
  | "NO_PRIOR_ADVERSE"
  | "PRIOR_ADVERSE_EXISTS"
  | "REPEAT_HISTORY_INDICATED";

export interface HistorySignal {
  entity_id: string;
  entity_name: string;
  total_cases: number;
  adverse_cases: number;
  repeat_count: number;
  signal_level: HistorySignalLevel;
  display_message: string;
  disclaimer: string;
}

// -------------------------------------------------------
// P2 Public Aggregate Dashboard
// -------------------------------------------------------
export interface DistrictMetric {
  district: string;
  total_inspections: number;
  compliant_count: number;
  non_compliant_count: number;
  review_count: number;
  compliance_rate_percent: number;
}

export interface CategoryMetric {
  category: string;
  total_inspections: number;
  compliant_count: number;
  non_compliant_count: number;
  review_count: number;
  compliance_rate_percent: number;
}

export interface PublicAggregate {
  total_inspections: number;
  compliant_count: number;
  non_compliant_count: number;
  review_count: number;
  compliance_rate_percent: number;
  districts: DistrictMetric[];
  categories: CategoryMetric[];
  disclaimer: string;
}

// -------------------------------------------------------
// Extended Scan with new fields
// -------------------------------------------------------
export type SourceType = "PHYSICAL_LABEL" | "ECOMMERCE_LISTING";

