"""Devanagari font registration for PDF output.

Known limitation: ReportLab maps glyphs in logical order and does not run OpenType
shaping, so Devanagari matras and conjuncts can be positioned incorrectly in the PDF
even with the right font registered. Hindi values are therefore also shown in the docket
as image crops taken from the original photograph, which is the evidentially stronger
form anyway — the crop is what was actually printed on the pack, not a re-typesetting
of it. Full shaping would need a HarfBuzz pass; tracked as a known gap.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.config import BASE_DIR

DEVANAGARI_FONT_NAME = "LabelLensDevanagari"

# Bundled font wins (portable across dev machines and Linux deploys); system paths are
# a convenience fallback so the docket is not full of tofu boxes during local demos.
CANDIDATES: list[tuple[Path, int]] = [
    (BASE_DIR / "app" / "assets" / "fonts" / "NotoSansDevanagari-Regular.ttf", 0),
    (Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"), 0),
    (Path("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc"), 0),
    (Path("/System/Library/Fonts/Kohinoor.ttc"), 0),
]

_registered: str | None = None
_attempted = False


def devanagari_font() -> str | None:
    """Register and return a Devanagari-capable font name, or None if none is available."""
    global _registered, _attempted
    if _attempted:
        return _registered
    _attempted = True

    for path, subfont_index in CANDIDATES:
        if not path.exists():
            continue
        try:
            font = (
                TTFont(DEVANAGARI_FONT_NAME, str(path), subfontIndex=subfont_index)
                if path.suffix.lower() == ".ttc"
                else TTFont(DEVANAGARI_FONT_NAME, str(path))
            )
            pdfmetrics.registerFont(font)
            _registered = DEVANAGARI_FONT_NAME
            return _registered
        except Exception:
            continue

    return None


def has_devanagari(text: str | None) -> bool:
    return bool(text) and any("ऀ" <= ch <= "ॿ" for ch in text)
