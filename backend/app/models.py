import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Entity(Base):
    """A manufacturer / packer / importer resolved across scans."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, index=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    license_no: Mapped[str | None] = mapped_column(String, nullable=True)
    fssai_no: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scans: Mapped[list["Scan"]] = relationship(back_populates="entity")
    cases: Mapped[list["Case"]] = relationship(back_populates="entity")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    officer_name: Mapped[str] = mapped_column(String)
    image_path: Mapped[str] = mapped_column(String)
    image_sha256: Mapped[str] = mapped_column(String, index=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    rule_version: Mapped[str] = mapped_column(String)
    ocr_lang: Mapped[str] = mapped_column(String, default="en")
    ocr_provider: Mapped[str] = mapped_column(String, default="mock")
    # Persisted OCR provenance — see app.services.ocr.OCRResult for field semantics.
    ocr_mode: Mapped[str] = mapped_column(String, default="online", nullable=True)
    ocr_fallback_from: Mapped[str | None] = mapped_column(String, nullable=True)
    ocr_fallback_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    verdict: Mapped[str] = mapped_column(String, default="PENDING")
    # Checks the capture could not support (e.g. numeral height without coordinates).
    not_assessed: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_food_item: Mapped[bool] = mapped_column(Boolean, default=False)
    is_imported: Mapped[bool] = mapped_column(Boolean, default=False)

    # The AI's verdict above is never overwritten by review. The officer's decision on
    # it is a separate, later fact: confirmed (the finding stands and, if it is a FIX or
    # REVIEW, opens a case), rejected (the officer determined the finding does not
    # stand), or needs_more_evidence (inconclusive from this capture). Null means no
    # officer has reviewed this scan yet.
    officer_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    officer_decision_by: Mapped[str | None] = mapped_column(String, nullable=True)
    officer_decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    officer_decision_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    entity: Mapped["Entity | None"] = relationship(back_populates="scans")
    declarations: Mapped[list["Declaration"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    violations: Mapped[list["Violation"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    # A scan can hold several entries: the original commit, plus one per officer
    # correction. Corrections are appended, never written over.
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        order_by="LedgerEntry.sequence",
    )
    reviews: Mapped[list["ScanReview"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", order_by="ScanReview.created_at"
    )
    case: Mapped["Case | None"] = relationship(
        back_populates="scan", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def ledger_entry(self) -> "LedgerEntry | None":
        """The entry that commits the record as it currently stands."""
        return self.ledger_entries[-1] if self.ledger_entries else None

    @property
    def amendment_count(self) -> int:
        return max(0, len(self.ledger_entries) - 1)


class Declaration(Base):
    """A single extracted label field, with evidence of where it was found."""

    __tablename__ = "declarations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"))
    field: Mapped[str] = mapped_column(String)
    value: Mapped[str | None] = mapped_column(String, nullable=True)
    present: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="illegible")  # verified | illegible | missing | officer_verified
    # Separate confidence tracks — see rule_engine.Declaration for semantics.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # legacy / overall
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # OCR-engine confidence
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # value-pattern match quality
    original_ocr_text: Mapped[str | None] = mapped_column(String, nullable=True)  # text before normalisation
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {x,y,w,h} relative 0-1
    height_px: Mapped[float | None] = mapped_column(Float, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="declarations")


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"))
    rule_id: Mapped[str] = mapped_column(String)
    clause: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    field: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="violations")


class LedgerEntry(Base):
    """One committed state of one scan, chained to the entry before it.

    The entry stores the payload it committed, not merely its hash, so the ledger is the
    authoritative history: an amended record keeps its original entry intact and
    verifiable rather than being rewritten.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, unique=True, autoincrement=True)
    prev_hash: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String)
    entry_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scan: Mapped["Scan"] = relationship(back_populates="ledger_entries")


class ManualOverride(Base):
    """Officer correction to an extracted field, kept for the audit trail."""

    __tablename__ = "manual_overrides"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"))
    declaration_id: Mapped[str] = mapped_column(ForeignKey("declarations.id"))
    officer_name: Mapped[str] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ScanReview(Base):
    """Append-only log of every officer decision on a scan's AI verdict.

    `Scan.officer_decision` holds the current decision; this table keeps every decision
    ever recorded (an officer can re-review), the same append-only pattern as
    ManualOverride keeps for declaration corrections.
    """

    __tablename__ = "scan_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"))
    officer_name: Mapped[str] = mapped_column(String)
    decision: Mapped[str] = mapped_column(String)  # confirmed | rejected | needs_more_evidence
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scan: Mapped["Scan"] = relationship(back_populates="reviews")


class Case(Base):
    """The enforcement case opened once an officer confirms a FIX or REVIEW verdict.

    A confirmed minor (FIX) finding opens a correction-notice track; a confirmed
    serious (REVIEW) finding opens a formal case — both carry an owner and a due date.
    A case left open past its due date is escalated automatically (checked lazily
    whenever cases are read, since this deployment has no background scheduler) rather
    than silently expiring. Findings only enter the seller's pattern history — the
    worklist's risk score — once the response window has closed one way or another;
    see risk_scoring.counted_violations. One scan carries at most one case: a further
    confirmed finding on the same scan (e.g. after a correction) reopens the same case
    rather than stacking a second one.
    """

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), unique=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    track: Mapped[str] = mapped_column(String)  # correction_notice | formal_case
    severity: Mapped[str] = mapped_column(String)  # worst violation severity at open time
    status: Mapped[str] = mapped_column(String, default="open")
    # open | escalated | resolved | unresolved | rejected
    officer_name: Mapped[str] = mapped_column(String)  # case owner
    rule_version: Mapped[str] = mapped_column(String)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response_days: Mapped[int] = mapped_column(Integer)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_to: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    # Snapshot of the scan's committed ledger-entry hash at the moment the case closed,
    # so the audit record ties the outcome to the exact evidence state it was decided on.
    evidence_hash_at_close: Mapped[str | None] = mapped_column(String, nullable=True)
    # Set when a case that was escalated is later closed: the supervisor's name stands
    # alongside the officer's on the record and on the docket's certificate.
    countersigned_by: Mapped[str | None] = mapped_column(String, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="case")
    entity: Mapped["Entity | None"] = relationship(back_populates="cases")

    @property
    def is_overdue(self) -> bool:
        now = _now()
        due = self.due_at if self.due_at.tzinfo else self.due_at.replace(tzinfo=now.tzinfo)
        return self.status == "open" and due < now

    @property
    def entity_name(self) -> str | None:
        return self.entity.name if self.entity else None

    @property
    def product_name(self) -> str | None:
        return self.scan.product_name if self.scan else None
