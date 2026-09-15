"""End-to-End API and Pipeline Scenario Tests (Step 5 & Step 6).

Tests full label processing through FastAPI TestClient and service pipeline
for all mandatory label scenarios:
- Manufacturer only
- Manufacturer + Packer
- Manufacturer + Packer + Importer
- Importer only
- Marketer only
- Hindi
- Mixed Hindi + English
- Low-quality / Glare / Unreadable / No declarations
"""
import io
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app
from app.services.extraction import extract_entity_declarations
from app.services.ocr import ManualTextProvider, OCRResult, TextBox
from app.services.ocr_normalize import find_entity_role_in_text

client = TestClient(app)


def _create_dummy_image_bytes(text: str = "TEST LABEL") -> bytes:
    """Helper to create a valid JPEG image in memory for testing upload endpoints."""
    img = Image.new("RGB", (400, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _signed_in_officer(client, auth_headers):
    """Recording an inspection requires an authenticated officer, so sign this
    client in for the duration of each test."""
    client.headers.update(auth_headers("officer"))
    yield
    client.headers.pop("Authorization", None)


class TestE2EApiPipeline:
    """Step 5: End-to-end API test with image upload."""

    def test_e2e_api_scan_endpoint(self, client):
        img_bytes = _create_dummy_image_bytes("MFG BY Apex Foods, Delhi")
        response = client.post(
            "/api/v1/scans",
            files={"image": ("label.jpg", img_bytes, "image/jpeg")},
            data={"officer_name": "Inspector E2E", "rule_version": "lmpc_2022_v2", "skip_quality_gate": "true"},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert "scan" in data
        scan = data["scan"]
        assert "id" in scan
        assert "verdict" in scan
        assert "ocr_provider" in scan
        assert "ocr_mode" in scan
        assert "declarations" in scan
        assert "entity_roles" in scan
        assert isinstance(scan["entity_roles"], list)


class TestLabelScenarios:
    """Step 6: Controlled Label Scenarios A through K."""

    def _extract_roles_for_lines(self, lines: list[str]):
        provider = ManualTextProvider()
        result = provider.extract_from_text("\n".join(lines))
        return extract_entity_declarations(result)

    def test_scenario_a_manufacturer_only(self):
        roles = self._extract_roles_for_lines(["Manufactured by ABC Foods Pvt Ltd, 123 Industrial Area, Delhi"])
        role_names = [r.role for r in roles]
        assert "manufacturer" in role_names
        assert "packer" not in role_names
        assert "importer" not in role_names

    def test_scenario_b_manufacturer_and_packer(self):
        roles = self._extract_roles_for_lines(["Manufactured & Packed by ABC Foods Pvt Ltd, Plot 4, Mumbai 400001"])
        role_names = [r.role for r in roles]
        assert "manufacturer" in role_names
        assert "packer" in role_names
        assert "importer" not in role_names

    def test_scenario_c_manufacturer_packer_importer_separate(self):
        lines = [
            "Manufactured by ABC Foods Ltd, Industrial Area, Pune 411026",
            "Packed by QuickPackers Pvt Ltd, Sector 18, Gurgaon 122001",
            "Imported by Global Traders Ltd, 12 Port Road, Mumbai 400001",
        ]
        roles = self._extract_roles_for_lines(lines)
        mfrs = [r for r in roles if r.role == "manufacturer"]
        pkrs = [r for r in roles if r.role == "packer"]
        imps = [r for r in roles if r.role == "importer"]
        assert len(mfrs) >= 1
        assert len(pkrs) >= 1
        assert len(imps) >= 1
        assert mfrs[0].entity_name != imps[0].entity_name

    def test_scenario_d_importer_only_must_not_become_manufacturer(self):
        roles = self._extract_roles_for_lines(["Imported by ABC Imports Ltd, New Delhi 110001"])
        role_names = [r.role for r in roles]
        assert "importer" in role_names
        assert "manufacturer" not in role_names

    def test_scenario_e_marketer_must_not_become_manufacturer(self):
        roles = self._extract_roles_for_lines(["Marketed by ABC Marketing Ltd, New Delhi"])
        role_names = [r.role for r in roles]
        assert "manufacturer" not in role_names
        assert "importer" not in role_names

    def test_scenario_f_hindi_manufacturer(self):
        text = "निर्माता: कामधेनु डेयरी उद्योग, जयपुर 302029"
        hits = find_entity_role_in_text(text)
        assert any(h[2] == "manufacturer" for h in hits)

    def test_scenario_g_mixed_hindi_english(self):
        lines = [
            "Net Qty: 500 g",
            "निर्माता: कामधेनु डेयरी, जयपुर 302029",
            "Packed by: Apex Packagers, Sector 5, Noida 201301",
        ]
        hits = find_entity_role_in_text("\n".join(lines))
        detected_roles = {h[2] for h in hits}
        assert "manufacturer" in detected_roles
        assert "packer" in detected_roles

    def test_scenario_h_low_quality_unreadable(self, client):
        """Unreadable image produces low confidence or missing declarations gracefully."""
        img_bytes = _create_dummy_image_bytes("x")
        response = client.post(
            "/api/v1/scans",
            files={"image": ("label.jpg", img_bytes, "image/jpeg")},
            data={"officer_name": "TestOfficer", "rule_version": "lmpc_2022_v2", "skip_quality_gate": "true"},
        )
        assert response.status_code == 201
        data = response.json()
        scan = data["scan"]
        assert scan["verdict"] in ("FIX", "REVIEW", "PENDING")
        assert "declarations" in scan

    def test_scenario_k_image_with_no_relevant_declarations(self, client):
        """Image without label declarations returns appropriate review/not-assessed behavior."""
        img_bytes = _create_dummy_image_bytes("Random non-label text pattern")
        response = client.post(
            "/api/v1/scans",
            files={"image": ("label.jpg", img_bytes, "image/jpeg")},
            data={"officer_name": "TestOfficer", "rule_version": "lmpc_2022_v2", "skip_quality_gate": "true"},
        )
        assert response.status_code == 201
        data = response.json()
        scan = data["scan"]
        assert scan["verdict"] in ("FIX", "REVIEW")
