"""The tamper-evidence guarantees the docket relies on. If these break, the 65B claim
is not defensible, so they are tested rather than asserted in a pitch."""

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import evidence_chain, pipeline

LABEL_LINES = [
    "Common Name: Namkeen Mixture",
    "Manufactured by: Sunrise Foods Pvt Ltd, Plot 22, Pune 411026",
    "Net Quantity: 200 g",
    "MRP: Rs. 45.00",
    "Mfg Date: 07/2026",
    "Best Before: 07/2027",
    "Consumer Care: care@sunrisefoods.example",
    "FSSAI Lic No: 11522998000123",
]


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def label_image(tmp_path):
    def _make(name: str = "label.jpg") -> str:
        from app.seed import make_label_image

        path = tmp_path / name
        make_label_image(LABEL_LINES, path)
        return str(path)

    return _make


def add_scan(db, image_path: str, product: str = "Test Pack"):
    scan, _ = pipeline.run_scan(
        db,
        image_path=image_path,
        image_sha256=evidence_chain.sha256_file(image_path),
        officer_name="Insp. Test",
        raw_text="\n".join(LABEL_LINES),
        product_name=product,
        is_food_item=True,
    )
    return scan


def test_chain_verifies_after_multiple_scans(db, label_image):
    for i in range(3):
        add_scan(db, label_image(f"label{i}.jpg"), product=f"Pack {i}")
    result = evidence_chain.verify_chain(db)
    assert result["valid"] is True
    assert result["checked_entries"] == 3


def test_first_entry_links_to_genesis(db, label_image):
    scan = add_scan(db, label_image())
    assert scan.ledger_entry.prev_hash == evidence_chain.GENESIS_HASH
    assert scan.ledger_entry.sequence == 1


def test_editing_a_scan_record_breaks_the_chain(db, label_image):
    add_scan(db, label_image("a.jpg"), product="Pack A")
    scan_b = add_scan(db, label_image("b.jpg"), product="Pack B")
    add_scan(db, label_image("c.jpg"), product="Pack C")

    assert scan_b.verdict == "GO"
    scan_b.verdict = "FIX"  # an after-the-fact edit to a committed finding
    db.commit()

    result = evidence_chain.verify_chain(db)
    assert result["valid"] is False
    assert result["broken_at_sequence"] == 2
    assert "tampering" in result["detail"].lower()


def test_editing_the_evidence_image_breaks_the_chain(db, label_image):
    path = label_image()
    scan = add_scan(db, path)
    assert evidence_chain.verify_chain(db)["valid"] is True

    with Image.open(path) as img:
        edited = img.copy()
    edited.paste((255, 255, 255), (40, 200, 500, 260))  # erase the MRP line
    edited.save(path, quality=95)

    result = evidence_chain.verify_chain(db)
    assert result["valid"] is False
    assert result["broken_at_sequence"] == scan.ledger_entry.sequence
    assert "modified since capture" in result["detail"]


def test_payload_hash_is_independent_of_row_order(db, label_image):
    """Row order from the database must not affect the hash, or a verification run on
    another machine could report tampering where none occurred."""
    scan = add_scan(db, label_image())
    original = evidence_chain.payload_hash(evidence_chain.canonical_payload(scan))

    scan.declarations.reverse()
    assert evidence_chain.payload_hash(evidence_chain.canonical_payload(scan)) == original
