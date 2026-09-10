"""Benchmark every Nebius model that accepts images, on real LabelLens label reads."""

import base64
import io
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

sys.path.insert(0, "/Users/harshithkt/Desktop/SIH/backend")

from PIL import Image  # noqa: E402

from app.services import extraction, nebius  # noqa: E402
from app.services.ocr import TextBox  # noqa: E402

HINDI_TRUTH = [
    "सामान्य नाम: शुद्ध देसी घी",
    "निर्माता: Kamdhenu Dairy Udyog, Village Palri, Jaipur 302029",
    "शुद्ध मात्रा: 500 ml",
    "अधिकतम खुदरा मूल्य: Rs. 620.00",
    "निर्माण तिथि: 07/2026",
    "उपभोक्ता सेवा: 1800-180-4040",
    "Best Before: 07/2027",
    "FSSAI Lic No: 12218044000456",
]
HINDI_FIELDS = {
    "common_name", "manufacturer_details", "net_quantity", "mrp",
    "mfg_date", "consumer_care", "best_before", "fssai_license_no",
}

ENGLISH_TRUTH = [
    "Common Name: Namkeen Mixture",
    "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, MIDC Bhosari, Pune 411026",
    "Net Quantity: 200 g",
    "MRP: Rs. 45.00 (incl. of all taxes)",
    "Mfg Date: 07/2026",
    "Consumer Care: care@sunrisefoods.example, 1800-100-2020",
    "FSSAI Lic No: 11522998000123",
]
ENGLISH_FIELDS = {
    "common_name", "manufacturer_details", "net_quantity", "mrp",
    "mfg_date", "consumer_care", "fssai_license_no",
}


def tiny_image_url() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (255, 255, 255)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def accepts_images(model: str) -> tuple[bool, str]:
    try:
        nebius.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Reply with the word ok."},
                        {"type": "image_url", "image_url": {"url": tiny_image_url()}},
                    ],
                }
            ],
            max_tokens=8,
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)[:90]


def score(model: str, image: str, truth: list[str], fields: set[str]) -> dict:
    started = time.time()
    try:
        lines = nebius.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": nebius.READ_LABEL_PROMPT},
                        {"type": "image_url", "image_url": {"url": nebius.image_data_url(image)}},
                    ],
                }
            ],
            temperature=0.0,
            max_tokens=3000,
            json_object=True,
        )
        parsed = nebius.parse_json_response(lines).get("lines", [])
    except Exception as exc:
        return {"error": str(exc)[:80], "seconds": time.time() - started}

    texts = [(line.get("text") or "").strip() for line in parsed if (line.get("text") or "").strip()]
    boxes = [TextBox(text=t, bbox=None, confidence=0.0) for t in texts]
    found = {f for f, d in extraction.extract_declarations(boxes).items() if d.present}

    similarity = SequenceMatcher(
        None, " ".join(truth).replace(" ", ""), " ".join(texts).replace(" ", "")
    ).ratio()
    grounded = sum(1 for line in parsed if isinstance(line.get("bbox"), dict)
                   and float(line["bbox"].get("h") or 0) > 0.001)

    return {
        "fields": f"{len(found & fields)}/{len(fields)}",
        "field_pct": len(found & fields) / len(fields),
        "text_similarity": round(similarity, 3),
        "lines": len(texts),
        "expected_lines": len(truth),
        "grounded_boxes": grounded,
        "seconds": round(time.time() - started, 1),
    }


def main():
    models = [m for m in nebius.list_models() if "Embedding" not in m]
    print(f"Probing {len(models)} models for image support...\n")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(accepts_images, models))

    vision = [m for m, (ok, _) in zip(models, results) if ok]
    for model, (ok, err) in zip(models, results):
        if not ok:
            print(f"  ✗ {model:42} {err}")
    print()
    for model in vision:
        print(f"  ✓ {model}")

    print(f"\n{'=' * 96}\nReading real labels with the {len(vision)} vision-capable models\n{'=' * 96}")
    header = f"{'model':40} {'fields':>8} {'text sim':>9} {'lines':>10} {'boxes':>6} {'secs':>6}"

    for label, image, truth, fields in (
        ("HINDI  (seed_08.jpg)", "/Users/harshithkt/Desktop/SIH/backend/storage/images/seed_08.jpg", HINDI_TRUTH, HINDI_FIELDS),
        ("ENGLISH (seed_00.jpg)", "/Users/harshithkt/Desktop/SIH/backend/storage/images/seed_00.jpg", ENGLISH_TRUTH, ENGLISH_FIELDS),
    ):
        print(f"\n--- {label} ---")
        print(header)
        with ThreadPoolExecutor(max_workers=4) as pool:
            scored = list(pool.map(lambda m: (m, score(m, image, truth, fields)), vision))
        for model, result in sorted(
            scored, key=lambda r: (-r[1].get("field_pct", 0), -r[1].get("text_similarity", 0))
        ):
            if "error" in result:
                print(f"{model:40} ERROR {result['error']}")
            else:
                print(
                    f"{model:40} {result['fields']:>8} {result['text_similarity']:>9} "
                    f"{str(result['lines']) + '/' + str(result['expected_lines']):>10} "
                    f"{result['grounded_boxes']:>6} {result['seconds']:>6}"
                )


if __name__ == "__main__":
    main()
