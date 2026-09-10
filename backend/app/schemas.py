from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeclarationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    field: str
    value: str | None
    present: bool
    status: str
    confidence: float
    bbox: dict | None
    height_px: float | None


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
    verdict: str
    not_assessed: list[dict] = []
    product_name: str | None
    is_food_item: bool
    is_imported: bool
    declarations: list[DeclarationOut] = []
    violations: list[ViolationOut] = []
    ledger_entry: LedgerEntryOut | None = None


class ScanSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str | None
    verdict: str
    product_name: str | None
    captured_at: datetime
    rule_version: str


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
