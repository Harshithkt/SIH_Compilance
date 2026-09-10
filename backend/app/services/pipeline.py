"""The scan pipeline: capture -> quality gate -> read -> extract -> evaluate -> commit.

Committing to the hash-chained ledger is the last step and happens in the same
transaction as the scan record, so a scan can never exist outside the chain.
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import IMAGES_DIR, settings
from app.models import Declaration as DeclarationRow
from app.models import Entity, Scan, Violation
from app.services import evidence_chain, extraction, ocr, quality, rule_engine


class QualityGateRejected(Exception):
    def __init__(self, report: quality.QualityReport):
        self.report = report
        super().__init__("Capture quality gate rejected this frame")


def store_image(upload_stream, filename: str) -> tuple[Path, str]:
    suffix = Path(filename).suffix.lower() or ".jpg"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = IMAGES_DIR / stored_name
    with open(destination, "wb") as fh:
        shutil.copyfileobj(upload_stream, fh)
    return destination, evidence_chain.sha256_file(destination)


def _resolve_entity(db: Session, declarations: dict, name: str | None) -> Entity | None:
    if not name:
        return None
    existing = db.execute(select(Entity).where(Entity.name == name)).scalar_one_or_none()
    if existing:
        return existing

    entity = Entity(
        name=name,
        address=(declarations["manufacturer_details"].value or None)
        if declarations.get("manufacturer_details")
        else None,
        fssai_no=(declarations["fssai_license_no"].value or None)
        if declarations.get("fssai_license_no")
        else None,
    )
    db.add(entity)
    db.flush()
    return entity


def run_scan(
    db: Session,
    *,
    image_path: Path,
    image_sha256: str,
    officer_name: str,
    lang: str = "en",
    provider_preference: str | None = None,
    raw_text: str | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    product_name: str | None = None,
    is_food_item: bool = False,
    is_imported: bool = False,
    rule_version: str | None = None,
    skip_quality_gate: bool = False,
    captured_at: datetime | None = None,
) -> tuple[Scan, dict]:
    quality_report = quality.assess(image_path)
    if not quality_report.passed and not skip_quality_gate:
        raise QualityGateRejected(quality_report)

    if raw_text:
        provider = ocr.ManualTextProvider()
        boxes = provider.extract_from_text(raw_text)
    else:
        provider = ocr.get_provider(provider_preference or settings.ocr_provider)
        boxes = provider.extract(str(image_path), lang=lang)

    declarations = extraction.extract_declarations(boxes)
    version = rule_version or settings.active_rule_version
    rule_pack = rule_engine.get_rule_pack(version)
    context = {"is_food_item": is_food_item, "is_imported": is_imported}
    verdict = rule_engine.evaluate(rule_pack, declarations, context)

    entity = _resolve_entity(db, declarations, extraction.resolve_entity_name(declarations))

    scan = Scan(
        entity_id=entity.id if entity else None,
        officer_name=officer_name,
        image_path=str(image_path),
        image_sha256=image_sha256,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        captured_at=captured_at or datetime.now(timezone.utc),
        rule_version=version,
        ocr_lang=lang,
        ocr_provider=provider.name,
        verdict=verdict.result,
        product_name=product_name,
        is_food_item=is_food_item,
        is_imported=is_imported,
    )
    db.add(scan)
    db.flush()

    for decl in declarations.values():
        db.add(
            DeclarationRow(
                scan_id=scan.id,
                field=decl.field,
                value=decl.value,
                present=decl.present,
                status=extraction.declaration_status(decl),
                confidence=next(
                    (b.confidence for b in boxes if decl.value and decl.value in b.text), 0.0
                ),
                bbox=decl.bbox,
                height_px=decl.height_px,
            )
        )

    for viol in verdict.violations:
        db.add(Violation(scan_id=scan.id, **viol))

    db.flush()
    db.refresh(scan)
    evidence_chain.append_scan(db, scan)
    db.commit()
    db.refresh(scan)

    return scan, quality_report.as_dict()
