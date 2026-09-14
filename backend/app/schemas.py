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


class ReviewIn(BaseModel):
    officer_name: str
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
    officer_name: str
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
    officer_decision: str | None
    officer_decision_by: str | None
    officer_decision_at: datetime | None
    officer_decision_notes: str | None
    declarations: list[DeclarationOut] = []
    violations: list[ViolationOut] = []
    entity_roles: list[EntityRoleOut] = []
    ledger_entry: LedgerEntryOut | None = None
    case: CaseOut | None = None


class ScanSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str | None
    verdict: str
    product_name: str | None
    captured_at: datetime
    rule_version: str
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
    officer_name: str
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
