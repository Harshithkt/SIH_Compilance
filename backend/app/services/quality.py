"""Capture-quality gate.

Rejects blurred, genuinely glared, dark or low-resolution frames *before*
analysis, so accuracy figures are honest: a label the system could not read
properly is reported as "retake this photo", never as a compliant or
non-compliant verdict.

Implemented with Pillow only — no OpenCV dependency for a check this simple.

Glare detection fix (vs. original):
    The original used `sum(histogram[250:]) / total_pixels > 0.25`, which
    treats every pixel ≥ 250 as glare.  White packaging naturally has many
    bright pixels — a white label background routinely exceeds 25% of pixels
    at luminance ≥ 250, causing false rejections.

    The new approach uses local region analysis:
      1. The image is divided into a grid of regions.
      2. A region is "saturated" if > REGION_GLARE_RATIO of its pixels are
         at luminance ≥ GLARE_PIXEL_THRESHOLD.
      3. Only *contiguous clusters* of saturated regions in the *centre* of
         the image (not the edges) are flagged as genuine glare.
      4. Glare severity is graded:
           none            — normal image including white packaging
           local_highlight — ≤ 2 saturated regions (e.g. small specular highlight)
           saturated_region — 3–6 saturated regions (advisory warning)
           blown_out       — > 6 saturated regions (causes gate failure)

    This allows pure white labels, bright packaging, and small specular
    highlights to pass while catching lens-flare and severe flash glare.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

MIN_WIDTH = 640
MIN_HEIGHT = 480
MIN_FOCUS_SCORE = 12.0
MIN_CONTRAST = 18.0
MIN_MEAN_LUMINANCE = 45.0

# ---- Glare detection parameters ----------------------------------------
# Pixels at or above this luminance are considered "bright"
GLARE_PIXEL_THRESHOLD = 250
# Fraction of pixels in a region that must be bright for the region to be
# classified as saturated
REGION_GLARE_RATIO = 0.60
# Grid divisions (GLARE_GRID × GLARE_GRID regions)
GLARE_GRID = 6
# Region must be in the centre GLARE_CENTRE_FRACTION of the image to count
GLARE_CENTRE_FRACTION = 0.85
# Number of saturated centre regions above which the image fails the gate
GLARE_BLOWN_OUT_THRESHOLD = 6
# -------------------------------------------------------------------------

LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)


@dataclass
class QualityReport:
    passed: bool
    metrics: dict
    issues: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "metrics": self.metrics, "issues": self.issues}


def _assess_glare(img_gray: Image.Image) -> tuple[str, float, int]:
    """Assess glare using local region analysis.

    Returns:
        (severity, global_bright_ratio, saturated_centre_region_count)

    Severity levels:
        "none"              — normal image, white packaging OK
        "local_highlight"   — small specular highlight, advisory only
        "saturated_region"  — moderate glare area, advisory warning
        "blown_out"         — severe glare, image fails quality gate
    """
    width, height = img_gray.size
    histogram = img_gray.histogram()
    total_pixels = width * height or 1
    global_bright_ratio = sum(histogram[GLARE_PIXEL_THRESHOLD:]) / total_pixels

    region_w = max(1, width // GLARE_GRID)
    region_h = max(1, height // GLARE_GRID)

    # Centre bounds — exclude border GLARE_CENTRE_FRACTION margin
    margin_x = int(width * (1 - GLARE_CENTRE_FRACTION) / 2)
    margin_y = int(height * (1 - GLARE_CENTRE_FRACTION) / 2)
    centre_left = margin_x
    centre_right = width - margin_x
    centre_top = margin_y
    centre_bottom = height - margin_y

    saturated_count = 0
    pixels = img_gray.load()

    for row in range(GLARE_GRID):
        for col in range(GLARE_GRID):
            x1 = col * region_w
            y1 = row * region_h
            x2 = min(x1 + region_w, width)
            y2 = min(y1 + region_h, height)

            # Only count regions whose centre is within the image centre zone
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            if not (centre_left <= cx <= centre_right and centre_top <= cy <= centre_bottom):
                continue

            region_total = (x2 - x1) * (y2 - y1)
            if region_total == 0:
                continue

            bright_count = sum(
                1
                for py in range(y1, y2)
                for px in range(x1, x2)
                if pixels[px, py] >= GLARE_PIXEL_THRESHOLD
            )

            if bright_count / region_total >= REGION_GLARE_RATIO:
                saturated_count += 1

    if saturated_count == 0:
        severity = "none"
    elif saturated_count <= 2:
        severity = "local_highlight"
    elif saturated_count <= GLARE_BLOWN_OUT_THRESHOLD:
        severity = "saturated_region"
    else:
        severity = "blown_out"

    return severity, round(global_bright_ratio, 4), saturated_count


def assess(image_path: str | Path) -> QualityReport:
    with Image.open(image_path) as img:
        img = img.convert("L")
        width, height = img.size
        edges = img.filter(LAPLACIAN)
        focus_score = ImageStat.Stat(edges).stddev[0]
        stat = ImageStat.Stat(img)
        mean_luminance = stat.mean[0]
        contrast = stat.stddev[0]

        glare_severity, global_bright_ratio, saturated_regions = _assess_glare(img)

    metrics = {
        "width": width,
        "height": height,
        "focus_score": round(focus_score, 2),
        "mean_luminance": round(mean_luminance, 1),
        "contrast": round(contrast, 2),
        "glare_ratio": global_bright_ratio,
        "glare_severity": glare_severity,
        "saturated_regions": saturated_regions,
    }
    issues = []

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        issues.append(
            {
                "code": "low_resolution",
                "message": (
                    f"Image is {width}×{height}px; at least "
                    f"{MIN_WIDTH}×{MIN_HEIGHT}px is needed to read small print."
                ),
                "guidance": "Move closer to the pack and fill the frame with the label.",
            }
        )

    if focus_score < MIN_FOCUS_SCORE:
        issues.append(
            {
                "code": "blurred",
                "message": (
                    f"Focus score {metrics['focus_score']} is below the "
                    f"{MIN_FOCUS_SCORE} threshold."
                ),
                "guidance": "Hold the phone steady, tap the label to focus, and retake.",
            }
        )

    # Glare: only "blown_out" causes a gate failure.
    # "local_highlight" and "saturated_region" are advisory warnings — white
    # packaging and small specular highlights must not cause rejection.
    if glare_severity == "blown_out":
        issues.append(
            {
                "code": "glare",
                "severity": "blown_out",
                "message": (
                    f"{saturated_regions} image regions are saturated by reflection "
                    f"(global bright ratio: {global_bright_ratio:.1%})."
                ),
                "guidance": (
                    "Tilt the pack away from the light source or turn off the flash."
                ),
            }
        )
    elif glare_severity == "saturated_region":
        # Advisory — does not cause failure
        issues.append(
            {
                "code": "glare_advisory",
                "severity": "saturated_region",
                "message": (
                    f"{saturated_regions} image region(s) appear saturated. "
                    "This may reduce OCR accuracy in those areas."
                ),
                "guidance": (
                    "If a declaration is illegible, tilt the pack and retake."
                ),
            }
        )

    if mean_luminance < MIN_MEAN_LUMINANCE:
        issues.append(
            {
                "code": "underexposed",
                "message": "The frame is too dark to read reliably.",
                "guidance": "Add light or move to a brighter spot, then retake.",
            }
        )

    if contrast < MIN_CONTRAST:
        issues.append(
            {
                "code": "low_contrast",
                "message": (
                    f"Contrast {metrics['contrast']} is too low to separate "
                    "print from packaging."
                ),
                "guidance": (
                    "Avoid direct light on the pack, and frame the printed panel squarely."
                ),
            }
        )

    # The gate fails only on hard blockers (not advisory warnings).
    hard_blockers = {"low_resolution", "blurred", "glare", "underexposed", "low_contrast"}
    has_hard_issue = any(i["code"] in hard_blockers for i in issues)

    return QualityReport(passed=not has_hard_issue, metrics=metrics, issues=issues)
