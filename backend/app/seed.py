"""Seed realistic demo inspections so the risk worklist has something to rank.

Run: python -m app.seed
Synthetic label images are generated locally (no real brands), each scan goes through the
real pipeline — same extraction, same rule engine, same ledger — so the demo data is
genuinely produced by the system rather than inserted behind it.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import IMAGES_DIR, settings
from app.database import Base, SessionLocal, engine
from app.models import Case, Declaration, Entity, LedgerEntry, ManualOverride, Scan, Violation
from app.services import case_engine, evidence_chain, pipeline

OFFICERS = ["Insp. R. Sharma", "Insp. M. Nair", "Insp. A. Bose"]

# (manufacturer line, product, label lines, food?, imported?)
DEMO_LABELS = [
    (
        "Sunrise Foods Pvt Ltd",
        "Masala Namkeen 200g",
        [
            "Common Name: Namkeen Mixture",
            "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, MIDC Bhosari, Pune 411026",
            "Net Quantity: 200 g",
            "MRP: Rs. 45.00 (incl. of all taxes)",
            "Mfg Date: 07/2026",
            "Consumer Care: care@sunrisefoods.example, 1800-100-2020",
            "FSSAI Lic No: 11522998000123",
        ],
        True,
        False,
    ),
    (
        "Sunrise Foods Pvt Ltd",
        "Aloo Bhujia 100g",
        [
            "Common Name: Bhujia",
            "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, MIDC Bhosari, Pune 411026",
            "Net Quantity: 100 g",
            "Mfg Date: 06/2026",
            "FSSAI Lic No: 11522998000123",
        ],
        True,
        False,
    ),
    (
        "Sunrise Foods Pvt Ltd",
        "Cornflakes 475g",
        [
            "Common Name: Breakfast Cereal",
            "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, MIDC Bhosari, Pune 411026",
            "Net Quantity: 475 g",
            "MRP: 320",
            "Consumer Care: care@sunrisefoods.example",
            "FSSAI Lic No: 1152299800",
        ],
        True,
        False,
    ),
    (
        "Global Trade Imports",
        "Olive Oil 500ml",
        [
            "Common Name: Refined Olive Oil",
            "Imported by: Global Trade Imports, 14 Dockyard Road, Mumbai 400010",
            "Net Quantity: 500 ml",
            "MRP: Rs. 899.00",
            "Mfg Date: 03/2026",
        ],
        True,
        True,
    ),
    (
        "Global Trade Imports",
        "Pasta 500g",
        [
            "Imported by: Global Trade Imports, 14 Dockyard Road, Mumbai 400010",
            "Net Quantity: 500 g",
            "MRP: Rs. 240.00",
        ],
        True,
        True,
    ),
    (
        "Global Trade Imports",
        "Canned Olives 300g",
        [
            "Common Name: Preserved Olives",
            "Imported by: Global Trade Imports, 14 Dockyard Road, Mumbai 400010",
            "Net Quantity: 300 g",
            "MRP: Rs. 410.00",
            "Mfg Date: 01/2026",
            "Best Before: 01/2028",
            "Consumer Care: hello@globaltrade.example",
        ],
        True,
        True,
    ),
    (
        "Deccan Household Products",
        "Detergent Powder 1kg",
        [
            "Common Name: Detergent Powder",
            "Manufactured by: Deccan Household Products, Survey 88, Medchal, Hyderabad 501401",
            "Net Quantity: 1 kg",
            "MRP: Rs. 165.00",
            "Mfg Date: 08/2026",
            "Consumer Care: 1800-425-9000, care@deccanhp.example",
        ],
        False,
        False,
    ),
    (
        "Deccan Household Products",
        "Floor Cleaner 500ml",
        [
            "Common Name: Floor Cleaner",
            "Manufactured by: Deccan Household Products, Survey 88, Medchal, Hyderabad 501401",
            "Net Quantity: 500 ml",
            "MRP: Rs. 99.00",
            "Mfg Date: 05/2026",
            "Consumer Care: 1800-425-9000",
        ],
        False,
        False,
    ),
    (
        "Kamdhenu Dairy Udyog",
        "Ghee 500ml",
        [
            "सामान्य नाम: शुद्ध देसी घी",
            "निर्माता: Kamdhenu Dairy Udyog, Village Palri, Jaipur 302029",
            "शुद्ध मात्रा: 500 ml",
            "अधिकतम खुदरा मूल्य: Rs. 620.00",
            "निर्माण तिथि: 07/2026",
            "उपभोक्ता सेवा: 1800-180-4040",
            "Best Before: 07/2027",
            "FSSAI Lic No: 12218044000456",
        ],
        True,
        False,
    ),
    (
        "Kamdhenu Dairy Udyog",
        "Paneer 200g",
        [
            "निर्माता: Kamdhenu Dairy Udyog, Village Palri, Jaipur 302029",
            "शुद्ध मात्रा: 200 g",
            "निर्माण तिथि: 09/2026",
        ],
        True,
        False,
    ),
]

MARKET_LOCATIONS = [
    (18.5204, 73.8567),  # Pune
    (19.0760, 72.8777),  # Mumbai
    (17.3850, 78.4867),  # Hyderabad
    (26.9124, 75.7873),  # Jaipur
]


FONT_CANDIDATES = [
    "C:/Windows/Fonts/Nirmala.ttc",  # Windows: covers Latin + Devanagari
    "C:/Windows/Fonts/arial.ttf",    # Windows: Latin
    "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",  # macOS: covers Latin + Devanagari
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", # Linux: Devanagari
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _label_font(size: int):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_label_image(lines: list[str], path) -> None:
    """Render a synthetic label image. The pipeline's quality gate is real, so these
    need to be legible: adequate size, contrast and sharpness. A Devanagari-capable font
    is required or the Hindi demo labels render as empty boxes.
    """
    width, height = 900, 760
    img = Image.new("RGB", (width, height), (247, 245, 238))
    draw = ImageDraw.Draw(img)
    draw.rectangle([12, 12, width - 12, height - 12], outline=(40, 40, 40), width=3)

    # Sized so a small pack's declarations clear Table I's own smallest (1mm) band —
    # see numeral_height_table1 — rather than every synthetic label being print-size
    # non-compliant regardless of what it declares.
    font = _label_font(34)
    y = 55
    for line in lines:
        draw.text((45, y), line, fill=(15, 15, 15), font=font)
        y += 62

    # Texture keeps the focus-variance metric realistic rather than artificially flat.
    for _ in range(2500):
        x_pos, y_pos = random.randint(15, width - 15), random.randint(15, height - 15)
        img.putpixel((x_pos, y_pos), (random.randint(90, 200),) * 3)
    img.save(path, quality=95)


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _apply_case_treatments(db, pending: list[tuple[Scan, str]]) -> None:
    """Drive each non-compliant demo scan through the officer-review / case workflow so
    the case list, worklist gating and dashboard have real, varied data to show —
    exactly the same functions the API calls, not data inserted behind them."""
    supervisor = settings.supervisor_role_name
    overdue_days = max(settings.correction_notice_response_days, settings.formal_case_response_days) + 5

    for scan, treatment in pending:
        officer = scan.officer_name

        if treatment == "leave_unreviewed":
            continue

        if treatment == "reject":
            case_engine.submit_decision(
                db, scan, officer_name=officer, decision="rejected",
                notes="On inspection the declaration was legible; the frame was under-lit.",
            )
            continue

        case_engine.submit_decision(db, scan, officer_name=officer, decision="confirmed")
        case = scan.case

        if treatment == "confirm_open":
            continue  # fresh case, still within its response window

        if treatment in ("confirm_overdue", "confirm_overdue_unresolved"):
            # Back-date the window so it reads as overdue once escalation runs below —
            # the seller was given the window and did not respond.
            case.opened_at = case.opened_at - timedelta(days=overdue_days)
            case.due_at = case.due_at - timedelta(days=overdue_days)
            db.commit()
            continue

        if treatment == "confirm_resolved":
            case_engine.close_case(
                db, case, closed_by=officer, resolution="resolved",
                notes="Reinspected within the window: corrected label on shelf.",
            )
            continue

    case_engine.escalate_overdue(db)

    # The one scan seeded to demonstrate an escalated case closing: closed only now,
    # after escalation, so it carries the supervisor's countersignature.
    for scan, treatment in pending:
        if treatment == "confirm_overdue_unresolved" and scan.case and scan.case.status == "escalated":
            case_engine.close_case(
                db, scan.case, closed_by=supervisor, resolution="unresolved",
                notes="No response within the window; referred for further enforcement action.",
            )


# Cycled across every non-compliant demo scan, in order, so the case workflow shows a
# realistic spread of states rather than every case looking alike: one left for the
# officer to review, one freshly confirmed and still within its window, one confirmed
# and already overdue (escalated below), one the seller corrected in time, one that
# escalated and was then closed unresolved by a supervisor (countersigned), and one the
# officer reviewed and rejected outright.
REVIEW_TREATMENTS = [
    "leave_unreviewed",
    "confirm_open",
    "confirm_overdue",
    "confirm_resolved",
    "confirm_overdue_unresolved",
    "reject",
]


def seed() -> None:
    random.seed(26034)
    reset_database()
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    pending_treatment: list[tuple[Scan, str]] = []

    try:
        for index, (_, product, lines, is_food, is_imported) in enumerate(DEMO_LABELS):
            image_path = IMAGES_DIR / f"seed_{index:02d}.jpg"
            make_label_image(lines, image_path)
            image_hash = evidence_chain.sha256_file(image_path)
            lat, lon = MARKET_LOCATIONS[index % len(MARKET_LOCATIONS)]

            # The first two inspections predate the 2022 amendment, so they stay pinned
            # to the rule pack in force on their inspection date — this is what the
            # rule-version comparison on a scan demonstrates.
            pre_amendment = index < 2
            rule_version = "2011-v1" if pre_amendment else None

            # Set before the ledger commit: the capture time is part of the hashed
            # payload, so back-dating it afterwards would (correctly) break the chain.
            captured_at = (
                datetime(2021, 9 - index, 14, 10, 30, tzinfo=timezone.utc)
                if pre_amendment
                # Spread the rest over the last 45 days so recency weighting is exercised.
                else now - timedelta(days=random.randint(0, 45), hours=random.randint(0, 23))
            )

            scan, _ = pipeline.run_scan(
                db,
                image_path=image_path,
                image_sha256=image_hash,
                officer_name=OFFICERS[index % len(OFFICERS)],
                lang="hi" if any(ord(c) > 2300 for c in "".join(lines)) else "en",
                raw_text="\n".join(lines),
                gps_lat=lat + random.uniform(-0.02, 0.02),
                gps_lon=lon + random.uniform(-0.02, 0.02),
                product_name=product,
                is_food_item=is_food,
                is_imported=is_imported,
                captured_at=captured_at,
                rule_version=rule_version,
            )

            if scan.verdict != "GO":
                treatment = REVIEW_TREATMENTS[len(pending_treatment) % len(REVIEW_TREATMENTS)]
                pending_treatment.append((scan, treatment))

        _apply_case_treatments(db, pending_treatment)

        counts = {
            "entities": db.query(Entity).count(),
            "scans": db.query(Scan).count(),
            "declarations": db.query(Declaration).count(),
            "violations": db.query(Violation).count(),
            "ledger_entries": db.query(LedgerEntry).count(),
            "overrides": db.query(ManualOverride).count(),
            "cases": db.query(Case).count(),
            "cases_by_status": {
                status: db.query(Case).filter(Case.status == status).count()
                for status in ("open", "escalated", "resolved", "unresolved", "rejected")
            },
        }
        print("Seeded:", counts)
        print("Ledger check:", evidence_chain.verify_chain(db)["detail"])
    finally:
        db.close()


if __name__ == "__main__":
    seed()
