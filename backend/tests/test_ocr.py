"""Comprehensive unit tests for the LabelLens OCR pipeline and fixes.

Covers:
  1. Tesseract word → line grouping (single-word, multi-word, multi-line, bbox union, weighted confidence)
  2. OCR confidence aggregation (single token, multi-token, missing tokens -> None)
  3. Context-restricted OCR character correction (headers only, numbers preserved)
  4. Field alias normalization (MRP, Net Qty, Manufacturer, Date variants)
  5. Multilingual extraction (English, Hindi, mixed lines)
  6. Glare assessment (white labels do not falsely trigger rejection)
  7. Provider fallback chain & provenance tracking (OCRResult contract, fallback recording)
  8. Offline/online contract parity
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services import extraction, ocr, ocr_normalize, quality
from app.services.ocr import OCRResult, TextBox, TesseractOCRProvider, run_ocr, OCRUnavailableError
from app.services.ocr_normalize import correct_ocr_errors, find_field_in_text, normalise_text


# ===========================================================================
# 1. Tesseract Word -> Line Grouping Tests
# ===========================================================================

def test_tesseract_grouping_single_word():
    """A single word forms a single text box with preserved bbox and confidence."""
    tsv_data = {
        "text": ["MRP:"],
        "left": [50],
        "top": [100],
        "width": [60],
        "height": [25],
        "conf": [92.0],
        "block_num": [1],
        "par_num": [1],
        "line_num": [1],
    }
    lines = TesseractOCRProvider._group_words_into_lines(tsv_data, img_w=1000, img_h=1000)
    assert len(lines) == 1
    box = lines[0]
    assert box.text == "MRP:"
    assert pytest.approx(box.confidence, 0.01) == 0.92
    assert box.bbox == {"x": 0.05, "y": 0.1, "w": 0.06, "h": 0.025}
    assert box.height_px == 25.0


def test_tesseract_grouping_multi_word_line():
    """Multiple words on the same line are merged with bbox union and length-weighted confidence."""
    tsv_data = {
        "text": ["Net", "Quantity:", "200", "g"],
        "left": [10, 50, 150, 200],
        "top": [100, 100, 102, 100],
        "width": [35, 90, 40, 20],
        "height": [20, 20, 18, 20],
        "conf": [90.0, 80.0, 95.0, 70.0],  # len: 3, 9, 3, 1 -> total len = 16
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
    }
    lines = TesseractOCRProvider._group_words_into_lines(tsv_data, img_w=1000, img_h=1000)
    assert len(lines) == 1
    box = lines[0]
    assert box.text == "Net Quantity: 200 g"
    # Bbox union: x1=10, y1=100, x2=220, y2=120
    assert box.bbox == {"x": 0.01, "y": 0.1, "w": 0.21, "h": 0.02}
    expected_conf = (3 * 0.90 + 9 * 0.80 + 3 * 0.95 + 1 * 0.70) / 16
    assert pytest.approx(box.confidence, 0.001) == expected_conf


def test_tesseract_grouping_multiline_and_blocks():
    """Distinct lines and distinct blocks produce separate TextBox entries in reading order."""
    tsv_data = {
        "text": ["Line1", "Word", "Line2", "Word"],
        "left": [10, 60, 10, 60],
        "top": [50, 50, 100, 100],
        "width": [45, 45, 45, 45],
        "height": [20, 20, 20, 20],
        "conf": [85.0, 85.0, 90.0, 90.0],
        "block_num": [1, 1, 2, 2],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
    }
    lines = TesseractOCRProvider._group_words_into_lines(tsv_data, img_w=1000, img_h=1000)
    assert len(lines) == 2
    assert lines[0].text == "Line1 Word"
    assert lines[1].text == "Line2 Word"


def test_tesseract_skips_whitespace_and_negative_confidence():
    """Words with negative confidence (Tesseract unassigned) or empty strings are ignored."""
    tsv_data = {
        "text": ["  ", "Valid", "   ", ""],
        "left": [10, 50, 100, 150],
        "top": [50, 50, 50, 50],
        "width": [20, 40, 20, 20],
        "height": [20, 20, 20, 20],
        "conf": [-1.0, 88.0, 0.0, -1.0],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
    }
    lines = TesseractOCRProvider._group_words_into_lines(tsv_data, img_w=1000, img_h=1000)
    assert len(lines) == 1
    assert lines[0].text == "Valid"


# ===========================================================================
# 2. Declaration Confidence Calculation Tests
# ===========================================================================

def test_calculate_confidence_multi_token():
    """Confidence calculation correctly prioritizes declaration tokens over full line tokens."""
    boxes = [
        TextBox(text="Net", bbox=None, confidence=0.90),
        TextBox(text="Quantity:", bbox=None, confidence=0.80),
        TextBox(text="200 g", bbox=None, confidence=0.96),
    ]
    conf = extraction.calculate_declaration_confidence("200 g", boxes, line_text="Net Quantity: 200 g")
    assert conf is not None
    # "200 g" token matches declaration "200 g" directly, giving 0.96 without diluting with unrelated line tokens
    assert pytest.approx(conf, 0.01) == 0.96



def test_calculate_confidence_missing_tokens_returns_none():
    """When no tokens match the declaration or line, return None (not 0.0)."""
    boxes = [
        TextBox(text="Some", bbox=None, confidence=0.95),
        TextBox(text="Other", bbox=None, confidence=0.92),
    ]
    conf = extraction.calculate_declaration_confidence("Rs. 45.00", boxes, line_text="MRP: Rs. 45.00")
    assert conf is None


# ===========================================================================
# 3. Context-Restricted Character Correction Tests
# ===========================================================================

def test_ocr_correction_restricted_to_keywords():
    """Character corrections (like l->I or 0->O) apply only within known keywords, preserving numeric values."""
    # Header keyword with typical OCR glitch: 'l' for 'I' in 'QUANTlTY'
    raw_header = "NET QUANTlTY: 100 ml"
    corrected = correct_ocr_errors(raw_header)
    assert "QUANTITY" in corrected
    assert "100 ml" in corrected  # Numbers like 100 must NOT have 0->O applied!

    # Country of origin with 0 for O: 'C0UNTRY' -> 'COUNTRY'
    raw_origin = "C0UNTRY OF 0RIGIN: INDIA"
    corrected_origin = correct_ocr_errors(raw_origin)
    assert "COUNTRY OF ORIGIN" in corrected_origin


def test_ocr_correction_does_not_corrupt_values():
    """Batch numbers, PIN codes, and dates containing '0' or '1' are never mangled."""
    raw_line = "Mfg Date: 01/2026 Batch: B001 PIN: 411026"
    corrected = correct_ocr_errors(raw_line)
    # The digits should remain intact
    assert "01/2026" in corrected
    assert "411026" in corrected


# ===========================================================================
# 4. Field Alias Normalization Tests
# ===========================================================================

@pytest.mark.parametrize(
    ("input_text", "expected_field"),
    [
        ("MAX RETAIL PRICE: Rs 99.00", "mrp"),
        ("M.R.P. (INCL. ALL TAXES): Rs 50", "mrp"),
        ("अधिकतम खुदरा मूल्य: ₹45", "mrp"),
        ("NET QTY: 500 g", "net_quantity"),
        ("NET WT: 1 kg", "net_quantity"),
        ("शुद्ध मात्रा: 250 ग्राम", "net_quantity"),
        ("PACKED & MARKETED BY: Apex Foods Ltd", "manufacturer_details"),
        ("MFD BY: Sunrise Agro, Pune", "manufacturer_details"),
        ("निर्माता: कामधेनु डेयरी", "manufacturer_details"),
        ("DATE OF MANUFACTURE: 05/2025", "mfg_date"),
        ("PACKED ON: 10/2025", "mfg_date"),
        ("CONSUMER COMPLAINTS: help@apex.example", "consumer_care"),
        ("COUNTRY OF ORIGIN: India", "country_of_origin"),
        ("MADE IN INDIA", "country_of_origin"),
        ("FSSAI LIC NO: 11522998000123", "fssai_license_no"),
    ],
)
def test_field_alias_recognition(input_text, expected_field):
    """Field aliases in English and Hindi are recognised accurately."""
    matches = find_field_in_text(input_text)
    assert len(matches) >= 1
    fields_found = [m[2] for m in matches]
    assert expected_field in fields_found


# ===========================================================================
# 5. Multilingual and Mixed Line Extraction
# ===========================================================================

def test_mixed_english_hindi_segmentation():
    """A line with Hindi and English declarations correctly separates both."""
    boxes = [
        TextBox(text="अधिकतम खुदरा मूल्य ₹50  Net Qty: 100 g", bbox=None, confidence=0.90)
    ]
    decls = extraction.extract_declarations(boxes)
    assert decls["mrp"].present is True
    assert "50" in (decls["mrp"].value or "")
    assert decls["net_quantity"].present is True
    assert "100 g" in (decls["net_quantity"].value or "")


# ===========================================================================
# 6. Glare Detection Assessment Tests
# ===========================================================================

def test_white_packaging_does_not_trigger_glare_rejection():
    """A pure white label with dark text has high bright pixels but must NOT be rejected as glare."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tmp_path = Path(tf.name)

    try:
        # Create a 600x400 predominantly white image (>80% white pixels)
        img = Image.new("RGB", (600, 400), (255, 255, 255))
        # Draw some dark text/boxes so it's not totally blank
        for y in range(50, 350, 40):
            for x in range(50, 500):
                img.putpixel((x, y), (10, 10, 10))
        img.save(tmp_path, quality=95)

        report = quality.assess(tmp_path)
        # Check that glare issue code is NOT raised as a rejection
        glare_issues = [issue for issue in report.issues if issue["code"] == "GLARE_DETECTED"]
        assert len(glare_issues) == 0, f"White label falsely triggered GLARE_DETECTED: {report.issues}"
        # Glare severity metric should exist
        assert "glare_severity" in report.metrics
    finally:
        tmp_path.unlink(missing_ok=True)


# ===========================================================================
# 7. Fallback Chain and Provenance Tracking Tests
# ===========================================================================

def test_provider_fallback_provenance():
    """When the primary provider returns empty or low confidence, run_ocr falls back and records provenance."""
    mock_result_fail = OCRResult(
        provider_used="mock_primary",
        mode="offline",
        language="en",
        text="",  # empty -> unusable
        regions=[],
        confidence=None,
    )
    mock_result_success = OCRResult(
        provider_used="tesseract",
        mode="offline",
        language="en",
        text="Net Quantity: 100 g",
        regions=[TextBox(text="Net Quantity: 100 g", bbox=None, confidence=0.88)],
        confidence=0.88,
    )

    class MockPrimary(ocr.OCRProvider):
        name = "mock_primary"
        mode = "offline"
        def extract(self, image_path, lang="en"):
            return mock_result_fail

    class MockSecondary(ocr.OCRProvider):
        name = "tesseract"
        mode = "offline"
        def extract(self, image_path, lang="en"):
            return mock_result_success

    with patch("app.services.ocr._OFFLINE_CHAIN", [MockPrimary, MockSecondary]):
        result = run_ocr("dummy.jpg", mode="offline")
        assert result.provider_used == "tesseract"
        assert result.fallback_from == "mock_primary"
        assert result.fallback_reason == "empty_result"


def test_ocr_unavailable_when_all_fail():
    """When every provider in the chain fails, OCRUnavailableError is raised."""
    class FailingProvider(ocr.OCRProvider):
        name = "failing"
        mode = "offline"
        def extract(self, image_path, lang="en"):
            raise RuntimeError("Hardware failure")

    with patch("app.services.ocr._OFFLINE_CHAIN", [FailingProvider]):
        with pytest.raises(OCRUnavailableError):
            run_ocr("dummy.jpg", mode="offline")


# ===========================================================================
# 8. OCRResult Contract Parity (Online vs Offline)
# ===========================================================================

def test_ocr_result_contract_fields():
    """Online and offline OCRResult instances must have identical field schemas."""
    online_res = OCRResult(
        provider_used="nebius",
        mode="online",
        language="en",
        text="Sample",
        regions=[TextBox(text="Sample", bbox={"x": 0, "y": 0, "w": 0.1, "h": 0.1}, confidence=0.95)],
        confidence=0.95,
    )
    offline_res = OCRResult(
        provider_used="tesseract",
        mode="offline",
        language="en",
        text="Sample",
        regions=[TextBox(text="Sample", bbox={"x": 0, "y": 0, "w": 0.1, "h": 0.1}, confidence=0.85)],
        confidence=0.85,
    )

    online_fields = set(online_res.__dataclass_fields__.keys())
    offline_fields = set(offline_res.__dataclass_fields__.keys())
    assert online_fields == offline_fields
    assert "fallback_from" in online_fields
    assert "fallback_reason" in online_fields
    assert "processing_metadata" in online_fields


def test_preferred_provider_aliases():
    """preferred_provider matches both canonical and aliased names ('nebius' -> 'nebius-vision')."""
    class MockNebius(ocr.OCRProvider):
        name = "nebius-vision"
        mode = "online"
        def extract(self, image_path, lang="en"):
            return OCRResult(
                provider_used="nebius-vision",
                mode="online",
                language=lang,
                text="Some text",
                regions=[TextBox(text="Some text", bbox=None, confidence=0.92)],
                confidence=0.92,
            )

    with patch("app.services.ocr._ONLINE_CHAIN", [MockNebius]):
        res1 = run_ocr("dummy.jpg", mode="online", preferred_provider="nebius")
        assert res1.provider_used == "nebius-vision"

        res2 = run_ocr("dummy.jpg", mode="online", preferred_provider="nebius-vision")
        assert res2.provider_used == "nebius-vision"


def test_low_confidence_fallback_retained_when_chain_exhausted():
    """If primary provider gives low-confidence text and secondary fails, low-conf text is preserved rather than throwing."""
    low_conf_result = OCRResult(
        provider_used="mock_primary",
        mode="offline",
        language="en",
        text="Low confidence but real text",
        regions=[TextBox(text="Low confidence but real text", bbox=None, confidence=0.35)],
        confidence=0.35,
    )

    class LowConfProvider(ocr.OCRProvider):
        name = "mock_primary"
        mode = "offline"
        def extract(self, image_path, lang="en"):
            return low_conf_result

    class FailingSecondary(ocr.OCRProvider):
        name = "tesseract"
        mode = "offline"
        def extract(self, image_path, lang="en"):
            raise RuntimeError("Engine unavailable")

    with patch("app.services.ocr._OFFLINE_CHAIN", [LowConfProvider, FailingSecondary]):
        result = run_ocr("dummy.jpg", mode="offline")
        assert result.provider_used == "mock_primary"
        assert result.confidence == 0.35
        assert result.text == "Low confidence but real text"


# ===========================================================================
# 9. OCR Union Bounding Box & Manual OCR Protection Tests
# ===========================================================================

def test_compute_declaration_evidence_union_bbox():
    """Multi-token declarations produce an enclosing union bbox covering all evidence tokens."""
    boxes = [
        TextBox(text="Manufactured", bbox={"x": 0.10, "y": 0.20, "w": 0.20, "h": 0.05}, confidence=0.90),
        TextBox(text="by", bbox={"x": 0.32, "y": 0.20, "w": 0.05, "h": 0.05}, confidence=0.88),
        TextBox(text="ABC", bbox={"x": 0.38, "y": 0.20, "w": 0.10, "h": 0.05}, confidence=0.95),
        TextBox(text="Foods", bbox={"x": 0.49, "y": 0.20, "w": 0.12, "h": 0.05}, confidence=0.92),
    ]
    conf, union_bbox, height_px = extraction.compute_declaration_evidence(
        "Manufactured by ABC Foods", boxes
    )
    assert union_bbox is not None
    # Union bbox: x1=0.10, y1=0.20, x2=0.61 (0.49+0.12), y2=0.25 (0.20+0.05)
    assert pytest.approx(union_bbox["x"], 0.001) == 0.10
    assert pytest.approx(union_bbox["y"], 0.001) == 0.20
    assert pytest.approx(union_bbox["w"], 0.001) == 0.51
    assert pytest.approx(union_bbox["h"], 0.001) == 0.05
    assert conf is not None
    assert 0.85 < conf < 0.95



def test_text_box_confidence_preserves_none():
    """Unknown or uncalculated token confidence remains None, NOT 0.0."""
    box = TextBox(text="Unknown", bbox={"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1}, confidence=None)
    assert box.confidence is None
    assert box.confidence != 0.0


def test_manual_text_never_replaces_ocr_silently(tmp_path):
    """If image OCR fails or produces no text, client-supplied raw_text must NOT silently become image-derived OCR.
    It must be tagged as MANUAL or fallback OCR provenance recorded.
    """
    from app.services import pipeline
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.seed import make_label_image

    db_path = tmp_path / "test_manual_protection.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    img_path = str(tmp_path / "blank_unrelated.jpg")
    make_label_image(["Unrelated Text Only"], img_path)

    # Simulating a call where image OCR fails or is offline mock returning empty
    failing_ocr = OCRResult(
        provider_used="tesseract",
        mode="offline",
        language="en",
        text="",
        regions=[],
        confidence=None
    )

    with patch("app.services.ocr.run_ocr", return_value=failing_ocr):
        scan, quality_dict = pipeline.run_scan(
            session,
            image_path=img_path,
            image_sha256="fake_sha256",
            officer_name="Inspector Clouseau",
            raw_text="Manufactured by Silent Overrider Pvt Ltd",  # Client-supplied manual override text
            product_name="Protection Pack"
        )
        # When raw_text is supplied by the client, the pipeline must mark the scan
        # with ocr_provider='manual' so it is distinguishable from real image OCR.
        # It must NEVER silently appear as 'tesseract' or any image-OCR provider.
        assert scan.ocr_provider == "manual"
        assert quality_dict is not None  # pipeline completed successfully


    session.close()



