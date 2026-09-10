"""Text-line geometry from the photograph itself.

Vision-language models read text well but do not reliably ground it, and typed entry has
no coordinates at all. Rather than fabricate boxes — unacceptable in an evidence docket —
line geometry is measured directly from the image by ink projection: rows containing dark
pixels form bands, each band is one printed line, and the band's extent gives the box and
the numeral height used by the Second Schedule check.

Lines are matched to recognised text by reading order, and only when the counts agree.
If they do not, no coordinates are recorded and the affected checks are reported as
not assessable.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

MAX_ANALYSIS_WIDTH = 1200
MIN_BAND_HEIGHT_PX = 6
BAND_GAP_TOLERANCE_PX = 4
# Pack edges, printed borders and the background around the label all read as ink and
# would otherwise merge every line into one band, so the outer frame is excluded.
EDGE_MARGIN_RATIO = 0.035


def detect_text_lines(image_path: str | Path) -> list[dict]:
    """Return one bbox per detected printed line, top to bottom.

    Coordinates are relative to the image (0-1); `height_px` is in the original image's
    pixels so it can be compared against type-size thresholds.
    """
    with Image.open(image_path) as source:
        image = ImageOps.grayscale(source)
        original_height = image.size[1]

        if image.size[0] > MAX_ANALYSIS_WIDTH:
            ratio = MAX_ANALYSIS_WIDTH / image.size[0]
            image = image.resize(
                (MAX_ANALYSIS_WIDTH, max(1, int(image.size[1] * ratio))), Image.LANCZOS
            )

        full_width, full_height = image.size
        margin_x = int(full_width * EDGE_MARGIN_RATIO)
        margin_y = int(full_height * EDGE_MARGIN_RATIO)
        image = image.crop((margin_x, margin_y, full_width - margin_x, full_height - margin_y))

        # Speckle (sensor noise, JPEG artefacts, print texture) puts a few dark pixels in
        # every row and would merge all lines into one band; a median pass removes it
        # without softening stroke edges the way a blur would.
        image = image.filter(ImageFilter.MedianFilter(3))

        width, height = image.size
        pixels = image.load()

        histogram = image.histogram()
        total = sum(histogram) or 1
        mean = sum(i * n for i, n in enumerate(histogram)) / total
        variance = sum(((i - mean) ** 2) * n for i, n in enumerate(histogram)) / total
        threshold = mean - 0.45 * (variance**0.5)

        min_ink = max(6, int(width * 0.012))
        row_has_ink = [
            sum(1 for x in range(width) if pixels[x, y] < threshold) >= min_ink
            for y in range(height)
        ]

        bands = _merge_bands(row_has_ink)
        scale_to_original = original_height / height

        lines = []
        for top, bottom in bands:
            if bottom - top < MIN_BAND_HEIGHT_PX:
                continue

            left, right = width, 0
            for y in range(top, bottom):
                for x in range(width):
                    if pixels[x, y] < threshold:
                        left = min(left, x)
                        break
                for x in range(width - 1, -1, -1):
                    if pixels[x, y] < threshold:
                        right = max(right, x)
                        break
            if right <= left:
                continue

            lines.append(
                {
                    # Coordinates are reported against the full image, not the analysed
                    # crop, so they line up with the stored photograph.
                    "bbox": {
                        "x": (left + margin_x) / full_width,
                        "y": (top + margin_y) / full_height,
                        "w": (right - left + 1) / full_width,
                        "h": (bottom - top) / full_height,
                    },
                    "height_px": (bottom - top) * scale_to_original,
                }
            )

    return lines


def _merge_bands(row_has_ink: list[bool]) -> list[tuple[int, int]]:
    bands: list[list[int]] = []
    start: int | None = None

    for y, has_ink in enumerate(row_has_ink):
        if has_ink and start is None:
            start = y
        elif not has_ink and start is not None:
            bands.append([start, y])
            start = None
    if start is not None:
        bands.append([start, len(row_has_ink)])

    merged: list[list[int]] = []
    for band in bands:
        if merged and band[0] - merged[-1][1] <= BAND_GAP_TOLERANCE_PX:
            merged[-1][1] = band[1]
        else:
            merged.append(band)

    return [(top, bottom) for top, bottom in merged]
