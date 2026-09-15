"""Pluggable text-recognition providers.

Provider hierarchy (auto mode):
    Online:  NebiusVisionProvider  → PaddleOCRProvider (fallback) → TesseractOCRProvider (fallback)
    Offline: PaddleOCRProvider     → TesseractOCRProvider (fallback)

The offline engine is PaddleOCR (PP-OCRv6, with PP-OCRv5 pinned for Devanagari);
Tesseract remains behind it as the dependency-free floor, since the paddlepaddle
runtime is a large optional install that some interpreters have no wheel for.

ManualTextProvider is NEVER part of the automatic fallback chain.  It must only be
activated by an explicit officer action (passing raw_text to the pipeline).  Silently
converting an OCR failure into manual text would make machine OCR evidence
indistinguishable from officer-typed text in the evidence docket — unacceptable.

Every OCR operation returns an OCRResult that records:
  • provider_used  — the provider that actually produced the text
  • mode           — "online" or "offline"
  • fallback_from  — the provider that was tried and failed (if any)
  • fallback_reason — why fallback was triggered

These fields are persisted on the Scan record so the evidence docket is honest about
how the text was obtained.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

OCRMode = Literal["online", "offline"]

LOW_CONFIDENCE_THRESHOLD = 0.40  # below this → try next provider


@dataclass
class TextBox:
    """One recognised text region with optional spatial evidence."""

    text: str
    bbox: dict | None  # {x, y, w, h} relative 0-1; None when position is unknown
    confidence: float | None = None  # 0–1; None when unknown/unmeasured
    height_px: float | None = None
    script: str | None = None  # "latin" | "devanagari" | "mixed" | None


@dataclass
class OCRResult:
    """Normalised OCR output contract shared by all providers.

    Both online and offline paths must produce this structure so downstream
    extraction and rule-engine code never needs separate branches.
    """

    provider_used: str
    mode: OCRMode
    language: str
    text: str                           # full concatenated text
    regions: list[TextBox]             # line/word regions in reading order
    confidence: float | None           # overall confidence; None = unknown
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fallback_from: str | None = None   # provider that was tried first and failed
    fallback_reason: str | None = None # "unavailable" | "low_confidence" | "empty_result" | "error"
    processing_metadata: dict = field(default_factory=dict)
    error: str | None = None           # non-fatal diagnostic; result still returned


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------


class OCRProvider(ABC):
    name: str
    mode: OCRMode = "online"

    @abstractmethod
    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        """Recognise text in *image_path* and return a normalised OCRResult."""
        ...

    def is_available(self) -> bool:  # noqa: D102
        """Return False when the provider cannot be initialised (missing key, binary, etc.)."""
        return True


# ---------------------------------------------------------------------------
# Tesseract provider — word → line grouping
# ---------------------------------------------------------------------------


class TesseractOCRProvider(OCRProvider):
    """Real OCR via pytesseract.

    Tesseract's `image_to_data` returns one row per recognised *word*.  This
    provider groups words into text lines using Tesseract's own block/paragraph/
    line numbering, then builds a union bounding box per line and aggregates
    confidence with a length-weighted mean (longer words are more reliable OCR
    anchors than short ones).
    """

    name = "tesseract"
    mode: OCRMode = "offline"

    def __init__(self) -> None:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("pytesseract/Pillow not installed") from exc

        import os
        if os.name == "nt":
            import pytesseract
            try:
                pytesseract.get_tesseract_version()
            except Exception:
                candidates = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
                ]
                for cand in candidates:
                    if os.path.exists(cand):
                        pytesseract.pytesseract.tesseract_cmd = cand
                        break

    def is_available(self) -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        import pytesseract
        from PIL import Image

        lang_map = {"en": "eng", "hi": "eng+hin", "en+hi": "eng+hin", "hi+en": "eng+hin"}
        tess_lang = lang_map.get(lang, "eng")

        img = Image.open(image_path)
        w, h = img.size
        data = pytesseract.image_to_data(
            img, lang=tess_lang, output_type=pytesseract.Output.DICT
        )
        regions = self._group_words_into_lines(data, img_w=w, img_h=h)

        full_text = "\n".join(r.text for r in regions)
        overall_conf: float | None = None
        valid_confs = [r.confidence for r in regions if r.confidence is not None and r.confidence > 0]
        if valid_confs:
            overall_conf = sum(valid_confs) / len(valid_confs)

        return OCRResult(
            provider_used=self.name,
            mode=self.mode,
            language=lang,
            text=full_text,
            regions=regions,
            confidence=overall_conf,
        )

    @staticmethod
    def _group_words_into_lines(data: dict, img_w: int, img_h: int) -> list[TextBox]:
        """Group word-level Tesseract data into lines with bbox union and length-weighted confidence."""
        lines: dict[tuple, list[int]] = {}
        for i, word in enumerate(data.get("text", [])):
            if not str(word).strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(i)

        regions: list[TextBox] = []
        for key in sorted(lines):
            indices = lines[key]
            words = [str(data["text"][i]).strip() for i in indices]
            line_text = " ".join(w for w in words if w)
            if not line_text:
                continue

            # Length-weighted mean confidence (conf == -1 means Tesseract gave up)
            confs = []
            lengths = []
            for i in indices:
                c = data["conf"][i]
                c_float = float(c) if c != "-1" and c != -1 else None
                word_text = str(data["text"][i]).strip()
                if c_float is not None and word_text and c_float >= 0:
                    confs.append(c_float / 100.0)
                    lengths.append(len(word_text))

            if confs:
                total_len = sum(lengths)
                line_conf: float | None = (
                    sum(c * l for c, l in zip(confs, lengths)) / total_len
                    if total_len
                    else None
                )
            else:
                line_conf = None

            # Union bounding box for the line (relative 0-1)
            lefts = [data["left"][i] for i in indices]
            tops = [data["top"][i] for i in indices]
            rights = [data["left"][i] + data["width"][i] for i in indices]
            bottoms = [data["top"][i] + data["height"][i] for i in indices]

            x1, y1, x2, y2 = min(lefts), min(tops), max(rights), max(bottoms)

            bbox: dict | None = None
            height_px: float | None = None
            if img_w > 0 and img_h > 0 and x2 > x1 and y2 > y1:
                bbox = {"x": x1 / img_w, "y": y1 / img_h, "w": (x2 - x1) / img_w, "h": (y2 - y1) / img_h}
                height_px = float(y2 - y1)

            regions.append(
                TextBox(
                    text=line_text,
                    bbox=bbox,
                    confidence=line_conf,
                    height_px=height_px,
                )
            )
        return regions


# ---------------------------------------------------------------------------
# Nebius Vision provider (online)
# ---------------------------------------------------------------------------


class NebiusVisionProvider(OCRProvider):
    """Vision-language text recognition via Nebius Token Factory.

    Strong on Devanagari and on low-contrast, curved, glossy packs that trip
    classical OCR.  Requires network + NEBIUS_API_KEY.

    Note on bounding boxes: VLM-generated bounding boxes are recorded but
    treated with low trust — they are estimates, not measurements.  The layout
    pass (`layout.py`) measures actual ink positions from pixels.  VLM boxes
    are retained as advisory evidence in the OCRResult but not relied on for
    compliance checks.
    """

    name = "nebius-vision"
    mode: OCRMode = "online"

    def __init__(self) -> None:
        from app.services import nebius

        if not nebius.is_configured():
            raise RuntimeError("NEBIUS_API_KEY not set")
        self._nebius = nebius

    def is_available(self) -> bool:
        try:
            from app.services import nebius

            return nebius.is_configured()
        except Exception:
            return False

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        raw_lines = self._nebius.read_label(image_path, lang=lang)
        regions: list[TextBox] = []
        for line in raw_lines:
            text = (line.get("text") or "").strip()
            if not text:
                continue
            # VLM bbox retained as advisory — may be inaccurate (see docstring)
            raw_bbox = line.get("bbox")
            bbox: dict | None = None
            if isinstance(raw_bbox, dict) and all(
                k in raw_bbox for k in ("x", "y", "w", "h")
            ):
                bbox = raw_bbox  # kept advisory; layout.py measures authoritatively

            conf = float(line.get("confidence") or 0.0)
            regions.append(
                TextBox(
                    text=text,
                    bbox=bbox,
                    confidence=conf,
                    height_px=None,
                    script=line.get("script"),
                )
            )

        full_text = "\n".join(r.text for r in regions)
        valid_confs = [r.confidence for r in regions if r.confidence > 0]
        overall_conf = sum(valid_confs) / len(valid_confs) if valid_confs else None

        return OCRResult(
            provider_used=self.name,
            mode=self.mode,
            language=lang,
            text=full_text,
            regions=regions,
            confidence=overall_conf,
            processing_metadata={"vlm_bbox_advisory": True},
        )


# ---------------------------------------------------------------------------
# PaddleOCR provider (offline, guarded import)
# ---------------------------------------------------------------------------


class PaddleOCRProvider(OCRProvider):
    """Local OCR via PaddleOCR (PP-OCRv5 / PP-OCRv6) — primary offline provider.

    Speaks the PaddleOCR 3.x API — `PaddleOCR(..., ocr_version=...).predict(path)`
    returning `rec_texts` / `rec_scores` / `rec_polys`. The 2.x API this provider used
    to call (`use_angle_cls=`, `show_log=`, `.ocr(..., cls=True)`) no longer exists, so
    a 2.x install is reported unavailable rather than silently mis-parsed.

    Language: PP-OCRv6 covers Chinese, English, Japanese and 46 Latin-script
    languages. Devanagari is not among them — PaddleOCR recognises Hindi with
    `devanagari_PP-OCRv5_mobile_rec` — so a Hindi request pins PP-OCRv5 whatever
    version is configured, and records that substitution in the result metadata.

    The engine is an optional install (see requirements-paddle.txt): paddlepaddle is a
    large download and ships no wheel for some interpreters. Without it
    `is_available()` returns False and the chain falls through to Tesseract.
    """

    name = "paddleocr"
    mode: OCRMode = "offline"

    # Officer-facing language hint → PaddleOCR `lang` code. A mixed English/Hindi
    # label goes to the Devanagari model, which also recognises Latin script.
    _LANG_MAP = {"en": "en", "hi": "hi", "en+hi": "hi", "hi+en": "hi"}
    _DEVANAGARI_LANG = "hi"
    _DEVANAGARI_VERSION = "PP-OCRv5"

    def __init__(self) -> None:
        try:
            import paddleocr  # noqa: F401
        except Exception as exc:  # a missing paddlepaddle runtime raises more than ImportError
            raise RuntimeError(f"paddleocr unavailable: {exc}") from exc
        self._engines: dict[tuple[str, str], Any] = {}

    def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR
        except Exception:
            return False
        # predict() marks the 3.x API. Against a 2.x install this provider would fail
        # deep inside parsing instead of cleanly handing over to the next provider.
        return hasattr(PaddleOCR, "predict")

    def _engine(self, paddle_lang: str, version: str) -> Any:
        from app.config import settings

        key = (paddle_lang, version)
        if key not in self._engines:
            from paddleocr import PaddleOCR

            # Orientation classification and unwarping stay off: the pipeline already
            # runs its own preprocessing pass, and each extra module is another model
            # to download onto a field device.
            self._engines[key] = PaddleOCR(
                lang=paddle_lang,
                ocr_version=version,
                device=settings.paddle_device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=settings.paddle_use_textline_orientation,
            )
        return self._engines[key]

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        from app.config import settings

        paddle_lang = self._LANG_MAP.get(lang, "en")
        configured_version = settings.paddle_ocr_version
        version = (
            self._DEVANAGARI_VERSION
            if paddle_lang == self._DEVANAGARI_LANG
            else configured_version
        )

        pages = self._engine(paddle_lang, version).predict(str(image_path))
        regions = self._regions(pages, image_path)

        full_text = "\n".join(r.text for r in regions)
        confidences = [r.confidence for r in regions if r.confidence is not None]
        overall_conf = sum(confidences) / len(confidences) if confidences else None

        meta: dict = {
            "paddle_lang": paddle_lang,
            "ocr_version": version,
            "device": settings.paddle_device,
        }
        if version != configured_version:
            meta["ocr_version_override"] = (
                f"{configured_version} has no Devanagari recognition model; "
                f"read with {version} instead."
            )

        return OCRResult(
            provider_used=self.name,
            mode=self.mode,
            language=lang,
            text=full_text,
            regions=regions,
            confidence=overall_conf,
            processing_metadata=meta,
        )

    @classmethod
    def _regions(cls, pages: Any, image_path: str) -> list[TextBox]:
        from PIL import Image

        with Image.open(image_path) as img:
            img_w, img_h = img.size

        regions: list[TextBox] = []
        for page in pages or []:
            payload = cls._payload(page)
            texts = payload.get("rec_texts") or []
            scores = payload.get("rec_scores") or []
            # rec_polys are the recognised line quads; dt_polys are the raw detector
            # output, used only when a build omits the former.
            polys = payload.get("rec_polys")
            if polys is None or len(polys) == 0:
                polys = payload.get("dt_polys") or []

            for index, raw_text in enumerate(texts):
                text = (raw_text or "").strip()
                if not text:
                    continue
                confidence = float(scores[index]) if index < len(scores) else None
                bbox, height_px = cls._bbox(
                    polys[index] if index < len(polys) else None, img_w, img_h
                )
                regions.append(
                    TextBox(
                        text=text,
                        bbox=bbox,
                        confidence=confidence,
                        height_px=height_px,
                        script=cls._script(text),
                    )
                )
        return regions

    @staticmethod
    def _payload(page: Any) -> dict:
        """Normalise one predict() result into a plain mapping.

        PaddleOCR 3.x results behave like mappings; some builds expose the same
        payload nested under `.json["res"]`. Both are handled because this path
        cannot be exercised without the paddlepaddle runtime installed.
        """
        if isinstance(page, dict):
            return page
        data = getattr(page, "json", None)
        if isinstance(data, dict):
            return data.get("res", data)
        return {}

    @staticmethod
    def _bbox(poly: Any, img_w: int, img_h: int) -> tuple[dict | None, float | None]:
        """Axis-aligned box, relative to image size, from a 4-point quad."""
        if poly is None or len(poly) == 0 or img_w <= 0 or img_h <= 0:
            return None, None
        xs = [float(point[0]) for point in poly]
        ys = [float(point[1]) for point in poly]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        if x2 <= x1 or y2 <= y1:
            return None, None
        return (
            {
                "x": x1 / img_w,
                "y": y1 / img_h,
                "w": (x2 - x1) / img_w,
                "h": (y2 - y1) / img_h,
            },
            y2 - y1,
        )

    @staticmethod
    def _script(text: str) -> str:
        devanagari = any("ऀ" <= ch <= "ॿ" for ch in text)
        latin = any(ch.isascii() and ch.isalpha() for ch in text)
        if devanagari and latin:
            return "mixed"
        return "devanagari" if devanagari else "latin"


# ---------------------------------------------------------------------------
# Manual text provider (explicit officer action ONLY)
# ---------------------------------------------------------------------------


class ManualTextProvider(OCRProvider):
    """Officer-typed text — explicit manual entry only.

    This provider MUST NOT appear in any automatic fallback chain.
    It is activated only when the officer explicitly passes raw_text to the
    pipeline.  Putting typed text into an automatic fallback would make it
    indistinguishable from genuine OCR evidence in the docket.
    """

    name = "manual"
    mode: OCRMode = "offline"

    def extract_from_text(self, raw_text: str) -> OCRResult:
        """Create an OCRResult from officer-supplied typed text."""
        regions = [
            TextBox(text=line.strip(), bbox=None, confidence=1.0, height_px=None)
            for line in raw_text.splitlines()
            if line.strip()
        ]
        return OCRResult(
            provider_used=self.name,
            mode="offline",
            language="manual",
            text=raw_text.strip(),
            regions=regions,
            confidence=None,  # Officer entry has no OCR confidence
            processing_metadata={"source": "officer_typed"},
        )

    def extract(self, image_path: str, lang: str = "en") -> OCRResult:
        # Never called via automatic path; returns empty result as a safety net
        return OCRResult(
            provider_used=self.name,
            mode="offline",
            language=lang,
            text="",
            regions=[],
            confidence=None,
            error="ManualTextProvider.extract() called without officer text — this is a bug.",
        )


# ---------------------------------------------------------------------------
# OCR Manager — fallback chain with explicit provenance
# ---------------------------------------------------------------------------

# Ordered provider chains.  ManualTextProvider is deliberately excluded.
_ONLINE_CHAIN = [NebiusVisionProvider, PaddleOCRProvider, TesseractOCRProvider]
_OFFLINE_CHAIN = [PaddleOCRProvider, TesseractOCRProvider]

PROVIDER_ALIASES: dict[str, set[str]] = {
    "nebius": {"nebius", "nebius-vision"},
    "nebius-vision": {"nebius", "nebius-vision"},
    "paddle": {"paddle", "paddleocr"},
    "paddleocr": {"paddle", "paddleocr"},
    "tesseract": {"tesseract"},
}


class OCRUnavailableError(RuntimeError):
    """Raised when every provider in the chain has failed or is unavailable."""


def _is_result_usable(result: OCRResult) -> bool:
    """A result is usable when it has text and confidence above the threshold."""
    if not result.text.strip():
        return False
    if result.confidence is not None and result.confidence < LOW_CONFIDENCE_THRESHOLD:
        return False
    return True


def run_ocr(
    image_path: str,
    *,
    lang: str = "en",
    mode: OCRMode = "online",
    preferred_provider: str | None = None,
) -> OCRResult:
    """Run OCR using the appropriate provider chain, with explicit fallback provenance.

    Args:
        image_path: Path to the image file.
        lang: Language hint ('en', 'hi', 'en+hi').
        mode: 'online' (try network providers first) or 'offline' (local only).
        preferred_provider: Force a specific provider name ('nebius', 'paddleocr',
            'tesseract').  When specified, only that provider is tried (no fallback).

    Returns:
        OCRResult with provider_used, mode, fallback_from, fallback_reason populated.

    Raises:
        OCRUnavailableError: When every provider in the chain fails.
    """
    chain_classes = _ONLINE_CHAIN if mode == "online" else _OFFLINE_CHAIN

    # Filter to preferred provider if specified, supporting standard aliases
    if preferred_provider:
        target_names = PROVIDER_ALIASES.get(
            preferred_provider.lower(), {preferred_provider.lower()}
        )
        chain_classes = [
            cls
            for cls in chain_classes
            if getattr(cls, "name", "").lower() in target_names
        ]
        if not chain_classes:
            raise OCRUnavailableError(
                f"Requested provider '{preferred_provider}' is not in the "
                f"{'online' if mode == 'online' else 'offline'} chain."
            )

    last_provider_name: str | None = None
    last_failure_reason: str | None = None
    last_error: str | None = None
    best_low_conf_result: OCRResult | None = None

    for provider_cls in chain_classes:
        provider_name: str = provider_cls.name  # type: ignore[attr-defined]
        try:
            provider = provider_cls()
        except RuntimeError as exc:
            log.info("OCR provider %s unavailable: %s", provider_name, exc)
            last_provider_name = provider_name
            last_failure_reason = "unavailable"
            last_error = str(exc)
            continue

        if not provider.is_available():
            log.info("OCR provider %s reports itself unavailable", provider_name)
            last_provider_name = provider_name
            last_failure_reason = "unavailable"
            continue

        try:
            result = provider.extract(image_path, lang=lang)
        except Exception as exc:  # noqa: BLE001
            log.warning("OCR provider %s raised: %s", provider_name, exc)
            last_provider_name = provider_name
            last_failure_reason = "error"
            last_error = str(exc)
            continue

        if not result.text.strip():
            log.info("OCR provider %s returned empty result", provider_name)
            last_provider_name = provider_name
            last_failure_reason = "empty_result"
            continue

        if result.confidence is not None and result.confidence < LOW_CONFIDENCE_THRESHOLD:
            log.info(
                "OCR provider %s returned low confidence %.2f — trying next",
                provider_name,
                result.confidence,
            )
            # Retain the best candidate result in case subsequent providers fail
            if best_low_conf_result is None or (
                result.confidence is not None
                and (best_low_conf_result.confidence or 0.0) < result.confidence
            ):
                best_low_conf_result = result
                if last_provider_name:
                    best_low_conf_result.fallback_from = last_provider_name
                    best_low_conf_result.fallback_reason = last_failure_reason

            last_provider_name = provider_name
            last_failure_reason = "low_confidence"
            # Continue to next provider
            continue

        # Successful result — record fallback provenance if we didn't use first choice
        if last_provider_name:
            result.fallback_from = last_provider_name
            result.fallback_reason = last_failure_reason

        log.info(
            "OCR succeeded with provider=%s mode=%s conf=%s fallback_from=%s",
            result.provider_used,
            result.mode,
            result.confidence,
            result.fallback_from,
        )
        return result

    # If all high-confidence attempts failed, but an engine produced usable text, return it
    if best_low_conf_result is not None:
        log.warning(
            "All OCR providers exhausted without high confidence; returning best result from %s (conf=%s)",
            best_low_conf_result.provider_used,
            best_low_conf_result.confidence,
        )
        return best_low_conf_result

    # All providers exhausted
    raise OCRUnavailableError(
        f"All OCR providers failed for mode='{mode}'. "
        f"Last attempted: {last_provider_name}, reason: {last_failure_reason}. "
        f"Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Legacy compatibility — keeps existing code that calls get_provider() working
# ---------------------------------------------------------------------------


def get_provider(prefer: str = "auto") -> "OCRProvider":
    """Legacy helper preserved for backward compatibility.

    New code should call `run_ocr()` directly which provides explicit
    fallback provenance.  This function returns an instantiated provider
    using the old auto-selection logic.
    """
    if prefer in ("nebius", "nebius-vision", "auto"):
        try:
            return NebiusVisionProvider()
        except RuntimeError:
            if prefer in ("nebius", "nebius-vision"):
                raise

    if prefer in ("paddleocr", "paddle", "auto"):
        try:
            p = PaddleOCRProvider()
            if p.is_available():
                return p
        except RuntimeError:
            if prefer in ("paddleocr", "paddle"):
                raise

    if prefer in ("tesseract", "auto"):
        try:
            return TesseractOCRProvider()
        except RuntimeError:
            if prefer == "tesseract":
                raise

    # Never auto-fall to ManualTextProvider — that must be an explicit officer action
    raise OCRUnavailableError(
        "No OCR provider is available. "
        "Install pytesseract/Tesseract or configure NEBIUS_API_KEY."
    )
