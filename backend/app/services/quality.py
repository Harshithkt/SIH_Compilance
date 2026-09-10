"""Capture-quality gate.

Rejects blurred, glared, dark or low-resolution frames *before* analysis, so accuracy
figures are honest: a label the system could not read properly is reported as
"retake this photo", never as a compliant or non-compliant verdict.

Implemented with Pillow only (variance of a Laplacian kernel for focus, luminance
histogram for glare/exposure) — no OpenCV dependency for a check this simple.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

MIN_WIDTH = 640
MIN_HEIGHT = 480
MIN_FOCUS_SCORE = 12.0
# Packaging is usually light-coloured, so absolute brightness says little. What decides
# readability is clipped highlights (specular glare) and print-to-background contrast.
MAX_GLARE_RATIO = 0.25
MIN_CONTRAST = 18.0
MIN_MEAN_LUMINANCE = 45.0

LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)


@dataclass
class QualityReport:
    passed: bool
    metrics: dict
    issues: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "metrics": self.metrics, "issues": self.issues}


def assess(image_path: str | Path) -> QualityReport:
    with Image.open(image_path) as img:
        img = img.convert("L")
        width, height = img.size
        edges = img.filter(LAPLACIAN)
        focus_score = ImageStat.Stat(edges).stddev[0]
        stat = ImageStat.Stat(img)
        mean_luminance = stat.mean[0]
        contrast = stat.stddev[0]
        histogram = img.histogram()
        total_pixels = width * height
        glare_ratio = sum(histogram[250:]) / total_pixels if total_pixels else 0.0

    metrics = {
        "width": width,
        "height": height,
        "focus_score": round(focus_score, 2),
        "mean_luminance": round(mean_luminance, 1),
        "contrast": round(contrast, 2),
        "glare_ratio": round(glare_ratio, 4),
    }
    issues = []

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        issues.append(
            {
                "code": "low_resolution",
                "message": f"Image is {width}×{height}px; at least {MIN_WIDTH}×{MIN_HEIGHT}px is needed to read small print.",
                "guidance": "Move closer to the pack and fill the frame with the label.",
            }
        )
    if focus_score < MIN_FOCUS_SCORE:
        issues.append(
            {
                "code": "blurred",
                "message": f"Focus score {metrics['focus_score']} is below the {MIN_FOCUS_SCORE} threshold.",
                "guidance": "Hold the phone steady, tap the label to focus, and retake.",
            }
        )
    if glare_ratio > MAX_GLARE_RATIO:
        issues.append(
            {
                "code": "glare",
                "message": f"{glare_ratio:.1%} of the frame is blown out by reflection.",
                "guidance": "Tilt the pack away from the light source or turn off the flash.",
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
                "message": f"Contrast {metrics['contrast']} is too low to separate print from packaging.",
                "guidance": "Avoid direct light on the pack, and frame the printed panel squarely.",
            }
        )

    return QualityReport(passed=not issues, metrics=metrics, issues=issues)
