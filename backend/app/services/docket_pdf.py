"""Prosecution-ready evidence docket PDF.

Note on the statute: the Indian Evidence Act, 1872 was replaced by the Bharatiya Sakshya
Adhiniyam, 2023 (in force 01-07-2024). The electronic-records certificate formerly under
s.65B IEA is now s.63(4) BSA. The docket cites both so it reads correctly to officers who
know the provision by either name.

The system DRAFTS this certificate. Admissibility still depends on the officer signing it;
the PDF states that plainly rather than claiming auto-generated legal process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import DOCKETS_DIR
from app.models import Scan
from app.services import fonts
from app.services.rule_engine import get_rule_pack

CROPS_DIR = DOCKETS_DIR / "crops"
CROPS_DIR.mkdir(parents=True, exist_ok=True)

SEVERITY_COLOR = {"high": "#B00020", "medium": "#B26A00", "low": "#4A5568"}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocketTitle",
            parent=base["Title"],
            fontSize=16,
            spaceAfter=2 * mm,
        ),
        "subtitle": ParagraphStyle(
            "DocketSubtitle",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#4A5568"),
            spaceAfter=4 * mm,
        ),
        "h2": ParagraphStyle(
            "DocketH2",
            parent=base["Heading2"],
            fontSize=11.5,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
            textColor=colors.HexColor("#1A202C"),
        ),
        "body": ParagraphStyle("DocketBody", parent=base["Normal"], fontSize=9, leading=12.5),
        "small": ParagraphStyle(
            "DocketSmall",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#4A5568"),
        ),
        "mono": ParagraphStyle(
            "DocketMono", parent=base["Normal"], fontName="Courier", fontSize=7.5, leading=10
        ),
        "legal": ParagraphStyle(
            "DocketLegal",
            parent=base["Normal"],
            fontSize=9,
            leading=14,
            alignment=TA_JUSTIFY,
        ),
    }


def _para(text: str | None, style, *, markup: bool = False) -> Paragraph:
    """Paragraph for label-derived text: escapes OCR content and swaps in a Devanagari
    font when the value contains Devanagari, so Hindi declarations are not rendered as
    empty boxes.
    """
    content = text if text else "—"
    if not markup:
        content = escape(content)
    if fonts.has_devanagari(text):
        font_name = fonts.devanagari_font()
        if font_name:
            style = ParagraphStyle(f"{style.name}Deva", parent=style, fontName=font_name)
    return Paragraph(content, style)


def _kv_table(rows: list[tuple[str, str]], styles) -> Table:
    data = [
        [Paragraph(f"<b>{k}</b>", styles["body"]), _para(v, styles["body"], markup=True)]
        for k, v in rows
    ]
    table = Table(data, colWidths=[52 * mm, 118 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _bbox_str(bbox: dict | None) -> str:
    if not bbox:
        return "not located on label"
    return (
        f"x={bbox['x']:.2f} y={bbox['y']:.2f} w={bbox['w']:.2f} h={bbox['h']:.2f} "
        "(relative to label image)"
    )


def _crop_evidence(scan: Scan) -> list[tuple[str, Path]]:
    """Cut each located declaration out of the original photograph.

    The crop is the primary evidence of what was printed, and it sidesteps the
    re-typesetting problem for Devanagari entirely.
    """
    image_path = Path(scan.image_path)
    if not image_path.exists():
        return []

    crops: list[tuple[str, Path]] = []
    try:
        from PIL import Image as PILImage

        with PILImage.open(image_path) as img:
            width, height = img.size
            for decl in sorted(scan.declarations, key=lambda d: d.field):
                if not decl.present or not decl.bbox:
                    continue
                bbox = decl.bbox
                pad_x, pad_y = 0.01 * width, 0.01 * height
                left = max(0, bbox["x"] * width - pad_x)
                top = max(0, bbox["y"] * height - pad_y)
                right = min(width, (bbox["x"] + bbox["w"]) * width + pad_x)
                bottom = min(height, (bbox["y"] + bbox["h"]) * height + pad_y)
                if right - left < 8 or bottom - top < 8:
                    continue

                crop_path = CROPS_DIR / f"{scan.id}_{decl.field}.png"
                img.crop((int(left), int(top), int(right), int(bottom))).save(crop_path)
                crops.append((decl.field, crop_path))
    except Exception:
        return []

    return crops


def build_docket(scan: Scan) -> Path:
    styles = _styles()
    generated_at = datetime.now(timezone.utc)
    out_path = DOCKETS_DIR / f"docket_{scan.id}.pdf"

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"LabelLens Evidence Docket {scan.id[:8]}",
        author="LabelLens",
    )

    rule_pack = get_rule_pack(scan.rule_version)
    entry = scan.ledger_entry
    story = []

    story.append(Paragraph("EVIDENCE DOCKET", styles["title"]))
    story.append(
        Paragraph(
            f"Legal Metrology (Packaged Commodities) Rules, 2011 &mdash; field inspection record"
            f"<br/>Docket ref: <b>LL-{scan.id[:8].upper()}</b> &nbsp;|&nbsp; Generated (UTC): {generated_at.strftime('%d-%m-%Y %H:%M:%S')}",
            styles["subtitle"],
        )
    )

    story.append(Paragraph("A. Inspection particulars", styles["h2"]))
    gps = (
        f"{scan.gps_lat:.6f}, {scan.gps_lon:.6f}"
        if scan.gps_lat is not None and scan.gps_lon is not None
        else "not recorded"
    )
    story.append(
        _kv_table(
            [
                ("Inspecting officer", escape(scan.officer_name)),
                ("Scan reference", scan.id),
                ("Commodity", escape(scan.product_name or "not recorded")),
                ("Captured at (UTC)", scan.captured_at.strftime("%d-%m-%Y %H:%M:%S")),
                ("Capture location (GPS)", gps),
                (
                    "Manufacturer / packer / importer",
                    escape(scan.entity.name) if scan.entity else "unresolved",
                ),
                ("Text-recognition source", f"{escape(scan.ocr_provider)} (language: {escape(scan.ocr_lang)})"),
                ("Verdict", scan.verdict),
            ],
            styles,
        )
    )

    story.append(Paragraph("B. Primary evidence &mdash; label image", styles["h2"]))
    image_path = Path(scan.image_path)
    if image_path.exists():
        try:
            from PIL import Image as PILImage

            with PILImage.open(image_path) as img:
                width, height = img.size
            display_w = 90 * mm
            display_h = display_w * height / width
            display_h = min(display_h, 110 * mm)
            display_w = display_h * width / height
            story.append(Image(str(image_path), width=display_w, height=display_h))
        except Exception:
            story.append(Paragraph("[image could not be rendered in this docket]", styles["small"]))
    else:
        story.append(
            Paragraph(
                "[image file not available at docket generation time]", styles["small"]
            )
        )
    story.append(Spacer(1, 3 * mm))
    story.append(
        _kv_table(
            [
                ("Image file", escape(image_path.name)),
                ("SHA-256 fingerprint", f"<font face='Courier' size='7.5'>{scan.image_sha256}</font>"),
            ],
            styles,
        )
    )

    story.append(Paragraph("C. Declarations extracted from the package", styles["h2"]))
    decl_rows = [
        [
            Paragraph("<b>Declaration</b>", styles["small"]),
            Paragraph("<b>Value read</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
            Paragraph("<b>Location on label</b>", styles["small"]),
        ]
    ]
    for decl in sorted(scan.declarations, key=lambda d: d.field):
        decl_rows.append(
            [
                Paragraph(decl.field.replace("_", " ").title(), styles["small"]),
                _para(decl.value, styles["small"]),
                Paragraph(decl.status, styles["small"]),
                Paragraph(_bbox_str(decl.bbox), styles["small"]),
            ]
        )
    decl_table = Table(decl_rows, colWidths=[38 * mm, 52 * mm, 22 * mm, 58 * mm], repeatRows=1)
    decl_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(decl_table)

    story.append(Paragraph("D. Rules applied at inspection time", styles["h2"]))
    story.append(
        _kv_table(
            [
                ("Rule pack version", rule_pack.version),
                ("Rule pack title", rule_pack.title),
                ("In force from", rule_pack.effective_date),
                (
                    "Rule pack SHA-256",
                    f"<font face='Courier' size='7.5'>{rule_pack.rule_hash()}</font>",
                ),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "The verdict recorded in this docket was computed against the rule pack identified above, "
            "as it stood on the date of inspection. Subsequent amendments to the rules do not alter "
            "this record; the pinned version can be re-verified against its SHA-256 at any time.",
            styles["small"],
        )
    )

    story.append(Paragraph("E. Contraventions found", styles["h2"]))
    if scan.violations:
        viol_rows = [
            [
                Paragraph("<b>Clause</b>", styles["small"]),
                Paragraph("<b>Requirement</b>", styles["small"]),
                Paragraph("<b>Severity</b>", styles["small"]),
                Paragraph("<b>Finding</b>", styles["small"]),
            ]
        ]
        for viol in scan.violations:
            viol_rows.append(
                [
                    Paragraph(viol.clause, styles["small"]),
                    Paragraph(viol.title, styles["small"]),
                    Paragraph(
                        f"<font color='{SEVERITY_COLOR.get(viol.severity, '#000000')}'>"
                        f"{viol.severity.upper()}</font>",
                        styles["small"],
                    ),
                    Paragraph(viol.message, styles["small"]),
                ]
            )
        viol_table = Table(viol_rows, colWidths=[30 * mm, 45 * mm, 20 * mm, 75 * mm], repeatRows=1)
        viol_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(viol_table)
    else:
        story.append(
            Paragraph("No contravention of the checked provisions was detected.", styles["body"])
        )

    if scan.not_assessed:
        story.append(Spacer(1, 3 * mm))
        story.append(
            Paragraph(
                "<b>Checks not assessable from this capture.</b> The following provisions could "
                "not be evaluated and are therefore neither alleged nor cleared:",
                styles["small"],
            )
        )
        for item in scan.not_assessed:
            story.append(
                Paragraph(
                    f"• {escape(item['clause'])} — {escape(item['title'])}: {escape(item['reason'])}",
                    styles["small"],
                )
            )

    crops = _crop_evidence(scan)
    if crops:
        story.append(Paragraph("F. Evidence crops from the original photograph", styles["h2"]))
        story.append(
            Paragraph(
                "Each crop below is cut directly from the photograph in Section B at the "
                "coordinates recorded for that declaration. No text has been re-typeset.",
                styles["small"],
            )
        )
        story.append(Spacer(1, 2 * mm))
        crop_rows = []
        for field_name, crop_path in crops:
            try:
                from PIL import Image as PILImage

                with PILImage.open(crop_path) as crop_img:
                    crop_w, crop_h = crop_img.size
                display_w = min(110 * mm, crop_w * 0.28 * mm)
                display_h = display_w * crop_h / crop_w
                crop_rows.append(
                    [
                        Paragraph(field_name.replace("_", " ").title(), styles["small"]),
                        Image(str(crop_path), width=display_w, height=display_h),
                    ]
                )
            except Exception:
                continue

        if crop_rows:
            crop_table = Table(crop_rows, colWidths=[38 * mm, 132 * mm])
            crop_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(crop_table)

    story.append(PageBreak())

    story.append(Paragraph("G. Integrity proof &mdash; hash-chained evidence ledger", styles["h2"]))
    if entry:
        story.append(
            _kv_table(
                [
                    ("Ledger entry no.", str(entry.sequence)),
                    ("Committed at (UTC)", entry.created_at.strftime("%d-%m-%Y %H:%M:%S")),
                    (
                        "Previous entry hash",
                        f"<font face='Courier' size='7.5'>{entry.prev_hash}</font>",
                    ),
                    (
                        "Record payload hash",
                        f"<font face='Courier' size='7.5'>{entry.payload_hash}</font>",
                    ),
                    (
                        "This entry hash",
                        f"<font face='Courier' size='7.5'>{entry.entry_hash}</font>",
                    ),
                ],
                styles,
            )
        )
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                "Each entry in the ledger is hashed together with the hash of the entry before it. "
                "Any later alteration of this record, of the label image, or of any earlier record in "
                "the ledger changes this entry hash and every entry after it, and is reported by the "
                "system's chain-verification routine identifying the exact entry at which the record "
                "was altered.",
                styles["small"],
            )
        )
    else:
        story.append(Paragraph("This scan has not yet been committed to the ledger.", styles["body"]))

    story.append(
        Paragraph(
            "H. Draft certificate under s.63(4), Bharatiya Sakshya Adhiniyam, 2023 "
            "(formerly s.65B, Indian Evidence Act, 1872)",
            styles["h2"],
        )
    )
    officer = escape(scan.officer_name)
    captured = scan.captured_at.strftime("%d-%m-%Y at %H:%M:%S hrs (UTC)")
    story.append(
        Paragraph(
            f"I, <b>{officer}</b>, holding the office of Inspector of Legal Metrology, do hereby certify that:"
            f"<br/><br/>"
            f"1. The electronic record annexed hereto, being a digital photograph of a pre-packaged commodity "
            f"together with the particulars extracted therefrom, was produced by the LabelLens field-inspection "
            f"system, a computer resource lawfully used by me in the regular course of my official duties, on "
            f"{captured}.<br/><br/>"
            f"2. Throughout the said period the said computer resource was operating properly, and the "
            f"information contained in the electronic record was regularly fed into it in the ordinary course of "
            f"the said activities.<br/><br/>"
            f"3. The said photograph bears the SHA-256 fingerprint "
            f"<font face='Courier' size='8'>{scan.image_sha256}</font>, computed at the time of capture, and the "
            f"record was committed to the system's append-only, hash-chained evidence ledger at entry no. "
            f"{entry.sequence if entry else '—'} bearing hash "
            f"<font face='Courier' size='8'>{entry.entry_hash if entry else '—'}</font>.<br/><br/>"
            f"4. The declarations recorded herein were assessed against rule pack version "
            f"<b>{rule_pack.version}</b> of the Legal Metrology (Packaged Commodities) Rules, 2011, being the "
            f"version in force on the date of inspection.<br/><br/>"
            f"5. To the best of my knowledge and belief, the contents of this record are true and correct.",
            styles["legal"],
        )
    )
    story.append(Spacer(1, 12 * mm))
    story.append(
        _kv_table(
            [
                ("Signature", ""),
                ("Name and designation", officer),
                ("Place", ""),
                ("Date", ""),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "<b>Note:</b> This certificate is generated in draft by LabelLens for the convenience of the "
            "certifying officer. It has no legal effect until it is verified, completed and signed by a person "
            "occupying a responsible official position in relation to the operation of the relevant device, as "
            "required by the statute. LabelLens does not issue legal process.",
            styles["small"],
        )
    )

    doc.build(story)
    return out_path
