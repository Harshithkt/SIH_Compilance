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
    verdict: Mapped[str] = mapped_column(String, default="PENDING")
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_food_item: Mapped[bool] = mapped_column(Boolean, default=False)
    is_imported: Mapped[bool] = mapped_column(Boolean, default=False)

    entity: Mapped["Entity | None"] = relationship(back_populates="scans")
    declarations: Mapped[list["Declaration"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    violations: Mapped[list["Violation"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    ledger_entry: Mapped["LedgerEntry | None"] = relationship(
        back_populates="scan", uselist=False, cascade="all, delete-orphan"
    )


class Declaration(Base):
    """A single extracted label field, with evidence of where it was found."""

    __tablename__ = "declarations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"))
    field: Mapped[str] = mapped_column(String)
    value: Mapped[str | None] = mapped_column(String, nullable=True)
    present: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="illegible")  # verified | illegible | missing
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
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
    """Append-only hash-chained evidence ledger. One entry per scan, chained to the prior entry."""

    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), unique=True)
    sequence: Mapped[int] = mapped_column(Integer, unique=True, autoincrement=True)
    prev_hash: Mapped[str] = mapped_column(String)
    payload_hash: Mapped[str] = mapped_column(String)
    entry_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scan: Mapped["Scan"] = relationship(back_populates="ledger_entry")


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
