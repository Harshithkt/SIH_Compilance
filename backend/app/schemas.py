from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeclarationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    field: str
    value: str | None
    present: bool
    status: str
    confidence: float | None = None  # overall/legacy
    ocr_confidence: float | None = None
    extraction_confidence: float | None = None
    original_ocr_text: str | None = None
    bbox: dict | None
    height_px: float | None


class EntityRoleOut(BaseModel):
    """Structured per-role entity extraction result for one scan.

    extraction_status is an EXTRACTION SIGNAL, not a compliance verdict:
      'found'   — name + recognizable address evidence detected by OCR
      'partial' — name detected, no address evidence
      'empty'   — role keyword matched but no usable content followed
    The rule engine (not this record) decides whether the legal requirement
    is satisfied.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str                          # manufacturer | packer | importer
    entity_name: str | None
    address_text: str | None
    raw_value: str | None              # full OCR segment (evidence)
    ocr_confidence: float | None
    extraction_confidence: float | None
    extraction_status: str             # found | partial | empty
    original_ocr_text: str | None      # un-normalised OCR line (evidence)
    bbox: dict | None
    height_px: float | None = None


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_id: str
    clause: str
    title: str
    field: str
    severity: str
    message: str
    bbox: dict | None


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scan_id: str
    entity_id: str | None
    entity_name: str | None
    product_name: str | None
    track: str
    severity: str
    status: str
    officer_name: str
    rule_version: str
    opened_at: datetime
    due_at: datetime
    response_days: int
    is_overdue: bool
    escalated_at: datetime | None
    escalated_to: str | None
    closed_at: datetime | None
    closed_by: str | None
    resolution_notes: str | None
    evidence_hash_at_close: str | None
    countersigned_by: str | None


# The officer on every record below is taken from the authenticated token, never from
# the request body — the name on a review, a correction or a closure is what the
# evidence record carries, so a client able to set it could sign another officer's name.
class ReviewIn(BaseModel):
    decision: str  # confirmed | rejected | needs_more_evidence
    notes: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scan_id: str
    officer_name: str
    decision: str
    notes: str | None
    created_at: datetime


class CaseCloseIn(BaseModel):
    resolution: str  # resolved | unresolved
    notes: str | None = None


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    prev_hash: str
    payload_hash: str
    entry_hash: str
    created_at: datetime


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str | None
    officer_name: str
    image_sha256: str
    gps_lat: float | None
    gps_lon: float | None
    captured_at: datetime
    rule_version: str
    ocr_lang: str
    ocr_provider: str
    ocr_mode: str = "online"
    ocr_fallback_from: str | None = None
    ocr_fallback_reason: str | None = None
    verdict: str
    not_assessed: list[dict] = []
    product_name: str | None
    is_food_item: bool
    is_imported: bool
    source_type: str = "PHYSICAL_LABEL"
    inspection_visit_id: str | None = None
    officer_decision: str | None
    officer_decision_by: str | None
    officer_decision_at: datetime | None
    officer_decision_notes: str | None
    declarations: list[DeclarationOut] = []
    violations: list[ViolationOut] = []
    entity_roles: list[EntityRoleOut] = []
    ledger_entry: LedgerEntryOut | None = None
    case: CaseOut | None = None
    physical_verifications: list["PhysicalVerificationOut"] = []


class ScanSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str | None
    verdict: str
    product_name: str | None
    captured_at: datetime
    rule_version: str
    source_type: str = "PHYSICAL_LABEL"
    inspection_visit_id: str | None = None
    officer_decision: str | None



class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str | None
    license_no: str | None
    fssai_no: str | None


class WorklistItem(BaseModel):
    entity: EntityOut
    scan_count: int
    violation_count: int
    high_severity_count: int
    risk_score: float
    repeat_offender: bool
    latest_verdict: str | None
    latest_scan_at: datetime | None


class LedgerVerifyOut(BaseModel):
    valid: bool
    checked_entries: int
    broken_at_sequence: int | None
    detail: str


class OverrideIn(BaseModel):
    declaration_id: str
    new_value: str
    reason: str


class OverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    declaration_id: str
    officer_name: str
    old_value: str | None
    new_value: str | None
    reason: str
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: str
    role: str
    is_active: bool


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class UserCreateIn(BaseModel):
    username: str
    full_name: str
    password: str
    role: str = "officer"


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_username: str
    actor_role: str
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict | None
    created_at: datetime


# --- P0 Physical Verification & P1-P2 Feature Schemas ---

class PhysicalVerificationCreate(BaseModel):
    scan_id: str
    case_id: str | None = None
    sample_number: int = 1
    declared_quantity: str
    declared_unit: str
    observed_quantity: float
    observed_unit: str
    notes: str | None = None


class PhysicalVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scan_id: str
    case_id: str | None
    entity_id: str | None
    sample_number: int
    declared_quantity: str
    declared_unit: str
    observed_quantity: float
    observed_unit: str
    normalized_declared_quantity: float
    normalized_observed_quantity: float
    shortfall: float
    applicable_rule_id: str
    applicable_rule_version: str
    applicable_mpe: float
    tolerance_basis: str
    result: str  # PASS | FAIL | REVIEW | NOT_ASSESSABLE
    verification_status: str  # CONFIRMED | DRAFT
    officer_username: str
    timestamp: datetime
    notes: str | None
    calculation_details: dict | None
    evidence_hash: str | None


class PriceAnomalyOut(BaseModel):
    scan_id: str
    product_name: str | None
    category: str | None
    price: float | None
    declared_quantity: str | None
    unit_price: float | None
    historical_avg_unit_price: float | None
    historical_sample_count: int
    signal: str  # NO_SIGNAL | LOW_SIGNAL | REVIEW | INSUFFICIENT_HISTORY
    explanation: str
    disclaimer: str = "Internal analytical signal — not a legal finding."


class ContactValidationOut(BaseModel):
    scan_id: str
    phone: str | None = None
    phone_status: str  # PASS | FAIL | NOT_ASSESSABLE
    phone_message: str | None = None
    email: str | None = None
    email_status: str  # PASS | FAIL | NOT_ASSESSABLE
    email_message: str | None = None
    disclaimer: str = "Syntax format validation only — does not confirm working contact status."


class MultiUnitConsistencyOut(BaseModel):
    inspection_visit_id: str
    unit_count: int
    status: str  # CONSISTENT | INCONSISTENT | INSUFFICIENT_EVIDENCE
    differing_declarations: list[dict] = []
    explanation: str


class HistorySignalOut(BaseModel):
    entity_id: str
    entity_name: str
    total_cases: int
    adverse_cases: int
    repeat_count: int
    signal_level: str  # NO_PRIOR_ADVERSE | PRIOR_ADVERSE_EXISTS | REPEAT_HISTORY_INDICATED
    display_message: str
    disclaimer: str = "Informational enforcement signal — not a legal determination."


class DistrictMetric(BaseModel):
    district: str
    total_inspections: int
    compliant_count: int
    non_compliant_count: int
    review_count: int
    compliance_rate_percent: float


class CategoryMetric(BaseModel):
    category: str
    total_inspections: int
    compliant_count: int
    non_compliant_count: int
    review_count: int
    compliance_rate_percent: float


class PublicAggregateOut(BaseModel):
    total_inspections: int
    compliant_count: int
    non_compliant_count: int
    review_count: int
    compliance_rate_percent: float
    districts: list[DistrictMetric] = []
    categories: list[CategoryMetric] = []
    disclaimer: str = "Anonymized aggregate inspection metrics for public transparency."


ScanOut.model_rebuild()

