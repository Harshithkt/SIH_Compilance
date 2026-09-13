"""The scan pipeline: capture → quality gate → preprocess → read → extract → evaluate → commit.

Committing to the hash-chained ledger is the last step and happens in the same
transaction as the scan record, so a scan can never exist outside the chain.

OCR changes:
  • Uses ocr.run_ocr() which provides explicit fallback provenance.
  • ManualTextProvider is only activated when the officer explicitly passes
    raw_text — never as an automatic fallback.
  • Preprocessing (preprocessing.py) runs between the quality gate and OCR.
    The preprocessed image is passed to the OCR provider; the original image
    is stored on disk unchanged as evidence.
  • OCR provenance (provider_used, mode, fallback_from, fallback_reason) is
    persisted on the Scan row.
  • Confidence is calculated with calculate_declaration_confidence() which
    uses length-weighted mean over matching tokens — not the broken substring
    search that always returned 0.0 for multi-word declarations.
  • All OCR exceptions are caught and converted to structured errors so the
    router can return appropriate HTTP status codes without stack traces.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import IMAGES_DIR, settings
from app.models import Declaration as DeclarationRow
from app.models import Entity, Scan, Violation
from app.services import (
    evidence_chain,
    extraction,
    layout,
    ocr,
    preprocessing,
    quality,
    rule_engine,
)

log = logging.getLogger(__name__)


class QualityGateRejected(Exception):
    def __init__(self, report: quality.QualityReport):
        self.report = report
        super().__init__("Capture quality gate rejected this frame")


class OCRFailed(Exception):
    """Raised when every OCR provider in the chain failed."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InvalidImageError(Exception):
    """Raised when the image cannot be decoded."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


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


def _attach_measured_geometry(
    boxes: list[ocr.TextBox], image_path: Path
) -> list[ocr.TextBox]:
    """Fill in line geometry measured from the photograph for boxes that have none.

    Detected lines are matched to recognised lines by reading order, and only
    when the counts agree — a mismatch means the association would be guesswork,
    and a box pointing at the wrong part of the label is worse than no box at all.
    """
    if not boxes or all(box.bbox for box in boxes):
        return boxes

    try:
        detected = layout.detect_text_lines(image_path)
    except Exception as exc:
        log.warning("Layout detection failed: %s — boxes remain unenhanced", exc)
        return boxes

    if len(detected) != len(boxes):
        log.debug(
            "Layout detected %d lines but OCR returned %d boxes — "
            "skipping geometry attachment to avoid mislabelling.",
            len(detected),
            len(boxes),
        )
        return boxes

    for box, line in zip(boxes, detected):
        if box.bbox is None:
            box.bbox = line["bbox"]
            box.height_px = line["height_px"]
    return boxes


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
    """Run the full inspection pipeline.

    Raises:
        QualityGateRejected — image quality below threshold (caller gets report)
        InvalidImageError   — image file cannot be decoded
        OCRFailed           — every OCR provider failed
        Other exceptions bubble up as generic server errors (caller logs + returns 500)
    """
    # ---- 1. Quality gate ----
    try:
        quality_report = quality.assess(image_path)
    except Exception as exc:
        raise InvalidImageError(f"Cannot read image file: {exc}") from exc

    if not quality_report.passed and not skip_quality_gate:
        raise QualityGateRejected(quality_report)

    # ---- 2. OCR ----
    ocr_result: ocr.OCRResult
    prep_meta: dict = {}

    if raw_text:
        # Explicit officer manual entry — never an automatic path
        manual_provider = ocr.ManualTextProvider()
        ocr_result = manual_provider.extract_from_text(raw_text)
        log.info("Using ManualTextProvider (officer-supplied raw_text)")
    else:
        # Determine online vs offline mode.
        # Heuristic: if a non-vision preference is given, or if Nebius is not
        # configured, treat as offline.  The API caller may also pass
        # provider_preference="tesseract" or "paddleocr" explicitly.
        from app.config import nebius_api_key

        if provider_preference in ("tesseract", "paddleocr", "paddle"):
            ocr_mode: ocr.OCRMode = "offline"
        elif provider_preference in ("nebius", "nebius-vision"):
            ocr_mode = "online"
        else:
            ocr_mode = "online" if nebius_api_key else "offline"

        # Adaptive preprocessing on original image (never overwrites it)
        try:
            prep_result = preprocessing.preprocess(image_path)
            ocr_image_path = prep_result.processed_path
            prep_meta = {
                "applied_steps": prep_result.applied_steps,
                "skipped_reason": prep_result.skipped_reason,
                "error": prep_result.error,
            }
        except Exception as exc:
            log.warning("Preprocessing raised unexpectedly: %s — using original", exc)
            ocr_image_path = str(image_path)

        try:
            ocr_result = ocr.run_ocr(
                ocr_image_path,
                lang=lang,
                mode=ocr_mode,
                preferred_provider=provider_preference
                if provider_preference not in (None, "auto")
                else None,
            )
        except ocr.OCRUnavailableError as exc:
            raise OCRFailed(str(exc)) from exc
        finally:
            # Clean up temp preprocessed file if it differs from original
            if ocr_image_path != str(image_path) and os.path.exists(ocr_image_path):
                try:
                    os.unlink(ocr_image_path)
                except OSError:
                    pass

    boxes = ocr_result.regions

    # ---- 3. Geometry attachment ----
    boxes = _attach_measured_geometry(boxes, image_path)

    # ---- 4. Declaration extraction ----
    declarations = extraction.extract_declarations(boxes)

    # ---- 5. Rule evaluation ----
    version = rule_version or settings.active_rule_version
    rule_pack = rule_engine.get_rule_pack(version)
    context = {"is_food_item": is_food_item, "is_imported": is_imported}
    verdict = rule_engine.evaluate(rule_pack, declarations, context)

    # ---- 6. Entity resolution ----
    entity = _resolve_entity(db, declarations, extraction.resolve_entity_name(declarations))

    # ---- 7. Persist scan ----
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
        ocr_provider=ocr_result.provider_used,
        ocr_mode=ocr_result.mode,
        ocr_fallback_from=ocr_result.fallback_from,
        ocr_fallback_reason=ocr_result.fallback_reason,
        verdict=verdict.result,
        not_assessed=verdict.not_assessed,
        product_name=product_name,
        is_food_item=is_food_item,
        is_imported=is_imported,
    )
    db.add(scan)
    db.flush()

    # ---- 8. Persist declarations with corrected confidence ----
    for decl in declarations.values():
        # Use the per-declaration OCR confidence from extraction.
        # Preserve null rather than substituting 0.0 — see Declaration.ocr_confidence.
        db.add(
            DeclarationRow(
                scan_id=scan.id,
                field=decl.field,
                value=decl.value,
                present=decl.present,
                status=extraction.declaration_status(decl),
                confidence=decl.ocr_confidence,              # may be None
                ocr_confidence=decl.ocr_confidence,          # explicit OCR track
                extraction_confidence=decl.extraction_confidence,
                original_ocr_text=decl.original_ocr_text,
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

    quality_dict = quality_report.as_dict()
    quality_dict["preprocessing"] = prep_meta if not raw_text else {}

    return scan, quality_dict
