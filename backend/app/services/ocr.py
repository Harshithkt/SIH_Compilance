"""Pluggable text-recognition providers.

Three interchangeable backends behind one interface:
  - NebiusVisionProvider: a vision-language model on Nebius Token Factory, which reads
    English + Devanagari label text with bounding boxes. This is the default.
  - TesseractOCRProvider: local OCR, for offline field use where no network is available.
  - ManualTextProvider: officer-typed text, which also backs the manual-override workflow.

All three return the same `list[TextBox]`, so the extraction and rule-engine layers never
learn which one produced the text — and the compliance verdict stays deterministic
regardless of backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TextBox:
    text: str
    bbox: dict | None  # {x, y, w, h} relative 0-1; None when the position is unknown
    confidence: float
    height_px: float | None = None


class OCRProvider(ABC):
    name: str

    @abstractmethod
    def extract(self, image_path: str, lang: str = "en") -> list[TextBox]:
        ...


class NebiusVisionProvider(OCRProvider):
    """Vision-language text recognition via Nebius Token Factory.

    Strong on Devanagari and on the low-contrast, curved, glossy packs that trip
    classical OCR. Requires network + NEBIUS_API_KEY; callers fall back to Tesseract
    for offline field mode.
    """

    name = "nebius-vision"

    def __init__(self):
        from app.services import nebius

        if not nebius.is_configured():
            raise RuntimeError("NEBIUS_API_KEY not set")
        self._nebius = nebius

    def extract(self, image_path: str, lang: str = "en") -> list[TextBox]:
        """Return recognised text only.

        Coordinates are deliberately discarded. Benchmarked against geometry measured
        from the same photographs, the boxes these models return are estimates dressed
        as measurements — identical line heights and perfectly uniform spacing, drifting
        progressively down the label (up to ~8% of image height at the bottom, enough to
        crop the wrong line). Position is established by app.services.layout instead,
        which measures it from the pixels.
        """
        return [
            TextBox(
                text=(line.get("text") or "").strip(),
                bbox=None,
                confidence=float(line.get("confidence") or 0.0),
                height_px=None,
            )
            for line in self._nebius.read_label(image_path, lang=lang)
            if (line.get("text") or "").strip()
        ]


class TesseractOCRProvider(OCRProvider):
    """Real OCR via pytesseract, used when the tesseract binary + language packs
    (eng, hin) are installed on the host. Falls back gracefully if unavailable.
    """

    name = "tesseract"

    def __init__(self):
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pytesseract/Pillow not installed") from exc

    def extract(self, image_path: str, lang: str = "en") -> list[TextBox]:
        import pytesseract
        from PIL import Image

        lang_map = {"en": "eng", "hi": "hin"}
        image = Image.open(image_path)
        w, h = image.size
        data = pytesseract.image_to_data(
            image, lang=lang_map.get(lang, "eng"), output_type=pytesseract.Output.DICT
        )
        boxes: list[TextBox] = []
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            conf = float(data["conf"][i]) if data["conf"][i] != "-1" else 0.0
            boxes.append(
                TextBox(
                    text=text.strip(),
                    bbox={
                        "x": data["left"][i] / w,
                        "y": data["top"][i] / h,
                        "w": data["width"][i] / w,
                        "h": data["height"][i] / h,
                    },
                    confidence=conf / 100.0,
                    height_px=float(data["height"][i]),
                )
            )
        return boxes


class ManualTextProvider(OCRProvider):
    """Fallback provider: treats officer-supplied raw text (one declaration per line,
    as 'field: value') as the OCR output, with synthetic bounding boxes. Used for
    demo/dev environments without a tesseract install, and for the manual-override
    field-capture flow described in the memo.
    """

    name = "manual"

    def extract_from_text(self, raw_text: str) -> list[TextBox]:
        """Typed entry carries no coordinates. Boxes are left empty here and measured
        from the photograph by the layout pass, never invented.
        """
        return [
            TextBox(text=line.strip(), bbox=None, confidence=1.0, height_px=None)
            for line in raw_text.splitlines()
            if line.strip()
        ]

    def extract(self, image_path: str, lang: str = "en") -> list[TextBox]:
        return []


def get_provider(prefer: str = "auto") -> OCRProvider:
    """Resolve a provider. 'auto' prefers the Nebius vision model, falls back to local
    Tesseract when there is no API key (offline field mode), then to manual entry.
    """
    if prefer in ("nebius", "auto"):
        try:
            return NebiusVisionProvider()
        except RuntimeError:
            if prefer == "nebius":
                raise

    if prefer in ("tesseract", "auto"):
        try:
            return TesseractOCRProvider()
        except RuntimeError:
            if prefer == "tesseract":
                raise

    return ManualTextProvider()
