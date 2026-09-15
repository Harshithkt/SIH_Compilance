"""Offline OCR via PaddleOCR (PP-OCRv5 / PP-OCRv6).

paddlepaddle publishes no wheel for this repo's interpreter, so the engine itself
cannot run here. These tests drive the provider against a stand-in shaped like the
PaddleOCR 3.x API — `PaddleOCR(...).predict()` returning `rec_texts` / `rec_scores` /
`rec_polys` — which pins the contract the provider depends on: that it asks for the
right model version per language, and turns quads into the relative bounding boxes the
rest of the pipeline measures against.
"""

import sys
import types

import pytest
from PIL import Image

from app.config import settings
from app.services import ocr
from app.services.ocr import OCRResult, PaddleOCRProvider, TextBox, run_ocr

IMAGE_W, IMAGE_H = 1000, 500

# One page of PP-OCRv5/v6 output: an English line, a Devanagari line, and a blank the
# provider must drop rather than emit as an empty declaration.
PAGE = {
    "rec_texts": ["Net Quantity: 200 g", "अधिकतम खुदरा मूल्य", "   "],
    "rec_scores": [0.94, 0.81, 0.10],
    "rec_polys": [
        [[100, 50], [400, 50], [400, 90], [100, 90]],
        [[100, 150], [500, 150], [500, 200], [100, 200]],
        [[0, 400], [10, 400], [10, 410], [0, 410]],
    ],
}


class FakePaddleOCR:
    """Records how it was constructed so the version/language choice can be asserted."""

    constructed: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakePaddleOCR.constructed.append(kwargs)

    def predict(self, path):
        self.last_path = path
        return [PAGE]


@pytest.fixture
def paddle(monkeypatch):
    FakePaddleOCR.constructed = []
    module = types.ModuleType("paddleocr")
    module.PaddleOCR = FakePaddleOCR
    monkeypatch.setitem(sys.modules, "paddleocr", module)
    return module


@pytest.fixture
def label(tmp_path):
    path = tmp_path / "label.jpg"
    Image.new("RGB", (IMAGE_W, IMAGE_H), (255, 255, 255)).save(path)
    return str(path)


class TestModelSelection:
    def test_english_uses_the_configured_version(self, paddle, label, monkeypatch):
        monkeypatch.setattr(settings, "paddle_ocr_version", "PP-OCRv6")

        result = PaddleOCRProvider().extract(label, lang="en")

        assert FakePaddleOCR.constructed[0]["ocr_version"] == "PP-OCRv6"
        assert FakePaddleOCR.constructed[0]["lang"] == "en"
        assert result.processing_metadata["ocr_version"] == "PP-OCRv6"
        assert "ocr_version_override" not in result.processing_metadata

    def test_hindi_pins_v5_because_v6_has_no_devanagari_model(
        self, paddle, label, monkeypatch
    ):
        monkeypatch.setattr(settings, "paddle_ocr_version", "PP-OCRv6")

        result = PaddleOCRProvider().extract(label, lang="hi")

        assert FakePaddleOCR.constructed[0]["ocr_version"] == "PP-OCRv5"
        assert FakePaddleOCR.constructed[0]["lang"] == "hi"
        # The substitution has to be visible on the record, not silent.
        assert "PP-OCRv5" in result.processing_metadata["ocr_version_override"]

    def test_mixed_language_capture_uses_the_devanagari_model(self, paddle, label):
        PaddleOCRProvider().extract(label, lang="en+hi")

        assert FakePaddleOCR.constructed[0]["lang"] == "hi"

    def test_engine_is_cached_per_language_and_version(self, paddle, label):
        provider = PaddleOCRProvider()

        provider.extract(label, lang="en")
        provider.extract(label, lang="en")
        provider.extract(label, lang="hi")

        # Loading a PP-OCR model is expensive; English must not be rebuilt.
        langs = [kwargs["lang"] for kwargs in FakePaddleOCR.constructed]
        assert langs == ["en", "hi"]

    def test_preprocessing_modules_stay_off(self, paddle, label):
        PaddleOCRProvider().extract(label, lang="en")

        kwargs = FakePaddleOCR.constructed[0]
        assert kwargs["use_doc_orientation_classify"] is False
        assert kwargs["use_doc_unwarping"] is False


class TestRegionParsing:
    def test_text_and_confidence_come_through(self, paddle, label):
        result = PaddleOCRProvider().extract(label, lang="en")

        assert [r.text for r in result.regions] == [
            "Net Quantity: 200 g",
            "अधिकतम खुदरा मूल्य",
        ]
        assert result.regions[0].confidence == pytest.approx(0.94)

    def test_blank_recognitions_are_dropped(self, paddle, label):
        result = PaddleOCRProvider().extract(label, lang="en")

        assert all(r.text.strip() for r in result.regions)
        assert len(result.regions) == 2

    def test_quads_become_relative_boxes(self, paddle, label):
        result = PaddleOCRProvider().extract(label, lang="en")

        box = result.regions[0]
        assert box.bbox == {
            "x": 100 / IMAGE_W,
            "y": 50 / IMAGE_H,
            "w": 300 / IMAGE_W,
            "h": 40 / IMAGE_H,
        }
        # Type-size rules measure in pixels, so the absolute height must survive.
        assert box.height_px == pytest.approx(40.0)

    def test_overall_confidence_averages_the_lines(self, paddle, label):
        result = PaddleOCRProvider().extract(label, lang="en")

        assert result.confidence == pytest.approx((0.94 + 0.81) / 2)

    def test_script_is_tagged_per_region(self, paddle, label):
        result = PaddleOCRProvider().extract(label, lang="hi")

        assert result.regions[0].script == "latin"
        assert result.regions[1].script == "devanagari"

    def test_detector_polys_are_used_when_recognition_polys_are_absent(
        self, paddle, label, monkeypatch
    ):
        page = {
            "rec_texts": ["MRP: Rs. 45.00"],
            "rec_scores": [0.9],
            "dt_polys": [[[0, 0], [200, 0], [200, 50], [0, 50]]],
        }
        monkeypatch.setattr(FakePaddleOCR, "predict", lambda self, path: [page])

        result = PaddleOCRProvider().extract(label, lang="en")

        assert result.regions[0].bbox is not None
        assert result.regions[0].height_px == pytest.approx(50.0)

    def test_results_nested_under_json_are_understood(self, paddle, label, monkeypatch):
        class Nested:
            json = {"res": PAGE}

        monkeypatch.setattr(FakePaddleOCR, "predict", lambda self, path: [Nested()])

        result = PaddleOCRProvider().extract(label, lang="en")

        assert result.regions[0].text == "Net Quantity: 200 g"

    def test_result_carries_offline_provenance(self, paddle, label):
        result = PaddleOCRProvider().extract(label, lang="en")

        assert result.provider_used == "paddleocr"
        assert result.mode == "offline"


class TestAvailability:
    def test_missing_runtime_reports_unavailable_rather_than_exploding(self, monkeypatch):
        # A None entry makes `import paddleocr` raise, standing in for an install
        # without the paddlepaddle runtime behind it.
        monkeypatch.setitem(sys.modules, "paddleocr", None)

        with pytest.raises(RuntimeError):
            PaddleOCRProvider()

    def test_paddleocr_2x_install_is_rejected(self, monkeypatch):
        class LegacyPaddleOCR:
            """2.x exposed ocr(..., cls=True) and no predict()."""

            def ocr(self, path, cls=True):
                return []

        module = types.ModuleType("paddleocr")
        module.PaddleOCR = LegacyPaddleOCR
        monkeypatch.setitem(sys.modules, "paddleocr", module)

        assert PaddleOCRProvider().is_available() is False

    def test_three_x_install_reports_available(self, paddle):
        assert PaddleOCRProvider().is_available() is True


class TestOfflineChain:
    """The provider is only useful if the offline chain actually reaches for it."""

    def test_paddleocr_leads_the_offline_chain(self, paddle, label):
        result = run_ocr(label, lang="en", mode="offline")

        assert result.provider_used == "paddleocr"
        assert result.mode == "offline"
        assert result.processing_metadata["ocr_version"] == settings.paddle_ocr_version

    def test_chain_hands_over_to_tesseract_when_the_engine_is_missing(
        self, monkeypatch, label
    ):
        monkeypatch.setitem(sys.modules, "paddleocr", None)

        class StubTesseract(ocr.OCRProvider):
            name = "tesseract"
            mode = "offline"

            def extract(self, image_path, lang="en"):
                return OCRResult(
                    provider_used="tesseract",
                    mode="offline",
                    language=lang,
                    text="Net Quantity: 200 g",
                    regions=[TextBox(text="Net Quantity: 200 g", bbox=None, confidence=0.8)],
                    confidence=0.8,
                )

        monkeypatch.setattr(
            ocr, "_OFFLINE_CHAIN", [PaddleOCRProvider, StubTesseract]
        )

        result = run_ocr(label, lang="en", mode="offline")

        assert result.provider_used == "tesseract"
        # The docket has to show why the better engine was not the one that read it.
        assert result.fallback_from == "paddleocr"
        assert result.fallback_reason == "unavailable"
