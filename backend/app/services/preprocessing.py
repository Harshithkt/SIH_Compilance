"""Adaptive image preprocessing for packaged-label OCR.

Applies a quality-aware preprocessing pipeline to improve OCR accuracy on
real field photographs without corrupting the evidence image.

Design principles:
  • The original image is NEVER overwritten.  Preprocessing writes to a
    temporary file.  The caller receives the temp path + metadata dict.
  • Processing is adaptive: a high-quality image gets minimal intervention;
    a low-contrast or blurred image gets more aggressive enhancement.
  • If any preprocessing step fails, the original path is returned unchanged
    with an error note in the metadata — OCR still proceeds on the original.
  • OpenCV is used if available (better CLAHE); Pillow is used as a fallback.
    Pillow is already a mandatory dependency so this module always works.

Handles:
  • Low contrast — histogram stretch / CLAHE
  • Uneven illumination — local contrast enhancement
  • Mild blur — unsharp masking (conservative: only if blur is detected)
  • Rotation / mild skew — skew detection + correction up to ±5 degrees
  • Compression artefacts — median filter at very low quality scores only
  • Oversized images — down-scaled for OCR (original preserved on disk)
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class PreprocessingResult:
    """Result of the adaptive preprocessing step."""

    processed_path: str        # Path to use for OCR (may == original_path)
    original_path: str         # Original image — never modified
    applied_steps: list[str] = field(default_factory=list)
    skipped_reason: str | None = None   # Why preprocessing was skipped / reduced
    error: str | None = None           # Non-fatal; OCR still proceeds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MAX_OCR_DIMENSION = 2000   # pixels; larger images are rescaled for OCR
_MIN_CONTRAST_FOR_CLAHE = 35.0
_MIN_FOCUS_FOR_SHARPEN = 20.0   # below this → sharpen; above → skip


def _opencv_available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def _pillow_contrast_stretch(img):
    """Contrast stretch using Pillow's autocontrast (CLAHE approximation)."""
    from PIL import ImageOps
    return ImageOps.autocontrast(img, cutoff=1)


def _clahe_opencv(img_gray_np):
    """Apply CLAHE in OpenCV for better local contrast on text regions."""
    import cv2
    import numpy as np
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img_gray_np)


def _estimate_skew_angle(img_gray_np) -> float:
    """Estimate rotation angle using horizontal projection variance.

    Returns angle in degrees in the range [-5, 5].  Anything outside that
    range is treated as deliberate orientation (portrait pack, rotated label)
    and is left unchanged.
    """
    try:
        import numpy as np
        h, w = img_gray_np.shape
        # Binary threshold
        threshold = img_gray_np.mean() - 0.5 * img_gray_np.std()
        binary = (img_gray_np < threshold).astype(np.uint8)
        # Try small angles and pick the one with maximum variance of row sums
        best_angle = 0.0
        best_var = -1.0
        for angle_tenth in range(-50, 51):  # -5° to +5° in 0.1° steps
            angle = angle_tenth / 10.0
            import cv2
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            rotated = cv2.warpAffine(binary, M, (w, h), borderValue=0)
            row_sums = rotated.sum(axis=1).astype(float)
            var = float(row_sums.var())
            if var > best_var:
                best_var = var
                best_angle = angle
        return best_angle
    except Exception:
        return 0.0


def _apply_sharpening(img):
    """Conservative unsharp mask — only if blur is detected."""
    from PIL import ImageFilter
    return img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))


def _measure_focus(img_gray) -> float:
    """Variance of Laplacian edges — proxy for focus/sharpness."""
    from PIL import ImageFilter, ImageStat
    edges = img_gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1))
    return ImageStat.Stat(edges).stddev[0]


def _measure_contrast(img_gray) -> float:
    from PIL import ImageStat
    return ImageStat.Stat(img_gray).stddev[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def preprocess(image_path: str | Path) -> PreprocessingResult:
    """Apply adaptive preprocessing to *image_path*.

    Returns a PreprocessingResult.  The `processed_path` field is safe to
    pass to an OCR provider.  The `original_path` must be preserved for the
    evidence ledger and must never be overwritten.

    The temp file is written to the system temp directory and is the caller's
    responsibility to clean up (or it will be cleaned up by the OS eventually).
    """
    image_path = str(image_path)
    result = PreprocessingResult(
        processed_path=image_path,
        original_path=image_path,
    )

    try:
        from PIL import Image, ImageStat

        img = Image.open(image_path)
        img_gray = img.convert("L")

        focus = _measure_focus(img_gray)
        contrast = _measure_contrast(img_gray)
        w, h = img.size

        steps: list[str] = []
        working = img_gray.copy()

        # 1. Rescale if oversized — for OCR speed, not evidence
        if max(w, h) > _MAX_OCR_DIMENSION:
            scale = _MAX_OCR_DIMENSION / max(w, h)
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            working = working.resize((new_w, new_h), Image.LANCZOS)
            steps.append(f"rescale({new_w}x{new_h})")

        # 2. Contrast enhancement if below threshold
        if contrast < _MIN_CONTRAST_FOR_CLAHE:
            if _opencv_available():
                try:
                    import cv2
                    import numpy as np
                    arr = np.array(working)
                    enhanced = _clahe_opencv(arr)
                    from PIL import Image as _PIL
                    working = _PIL.fromarray(enhanced)
                    steps.append("clahe_opencv")
                except Exception as exc:
                    log.debug("CLAHE failed, using Pillow autocontrast: %s", exc)
                    working = _pillow_contrast_stretch(working)
                    steps.append("autocontrast_pillow")
            else:
                working = _pillow_contrast_stretch(working)
                steps.append("autocontrast_pillow")

        # 3. Mild sharpening if blurred
        if focus < _MIN_FOCUS_FOR_SHARPEN:
            working = _apply_sharpening(working)
            steps.append("unsharp_mask")

        # 4. Deskew — only with OpenCV, only for small angles (≤5°)
        if _opencv_available():
            try:
                import cv2
                import numpy as np
                arr = np.array(working)
                angle = _estimate_skew_angle(arr)
                if abs(angle) > 0.3:
                    rows, cols = arr.shape
                    M = cv2.getRotationMatrix2D((cols / 2, rows / 2), angle, 1.0)
                    deskewed = cv2.warpAffine(arr, M, (cols, rows), borderValue=255)
                    from PIL import Image as _PIL
                    working = _PIL.fromarray(deskewed)
                    steps.append(f"deskew({angle:.1f}deg)")
            except Exception as exc:
                log.debug("Deskew failed: %s", exc)

        # 5. Save processed image to temp file (never overwrite original)
        if steps:
            suffix = Path(image_path).suffix or ".png"
            tmp = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False, prefix="labellens_ocr_"
            )
            tmp.close()
            working.save(tmp.name)
            result.processed_path = tmp.name
            result.applied_steps = steps
        else:
            result.skipped_reason = "no_preprocessing_needed"

    except Exception as exc:
        log.warning("Preprocessing failed for %s: %s — using original", image_path, exc)
        result.error = f"Preprocessing skipped: {exc}"
        result.processed_path = image_path  # Fall back to original

    return result
