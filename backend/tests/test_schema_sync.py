"""Reconciling a database file created before a model change.

Both paths matter to real deployments: an existing `labellens.db` was found missing
the OCR-provenance columns entirely, and carrying a `NOT NULL` on
`declarations.confidence` that the model now allows to be null — which made every
scan whose confidence was unknown fail to insert.
"""

from sqlalchemy import create_engine, inspect

from app.database import Base
from app.schema_sync import sync_schema

# The declarations table as it stood before the OCR-provenance columns were added:
# no ocr_confidence / extraction_confidence / original_ocr_text, and confidence NOT NULL.
LEGACY_DECLARATIONS = """
CREATE TABLE declarations (
    id VARCHAR NOT NULL,
    scan_id VARCHAR NOT NULL,
    field VARCHAR NOT NULL,
    value VARCHAR,
    present BOOLEAN NOT NULL,
    status VARCHAR NOT NULL,
    confidence FLOAT NOT NULL,
    bbox JSON,
    height_px FLOAT,
    PRIMARY KEY (id),
    FOREIGN KEY(scan_id) REFERENCES scans (id)
)
"""

RELAXED_DECLARATIONS = LEGACY_DECLARATIONS.replace("confidence FLOAT NOT NULL", "confidence FLOAT")


def _legacy_database(tmp_path, declarations_ddl: str):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE declarations")
        conn.exec_driver_sql(declarations_ddl)
        conn.exec_driver_sql(
            "INSERT INTO declarations (id, scan_id, field, value, present, status, confidence)"
            " VALUES ('d1', 's1', 'mrp', 'Rs. 45.00', 1, 'verified', 0.91)"
        )
    return engine


def _columns(engine, table: str) -> dict:
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


class TestRelaxingAConstraint:
    def test_not_null_is_relaxed_and_missing_columns_arrive(self, tmp_path):
        engine = _legacy_database(tmp_path, LEGACY_DECLARATIONS)

        sync_schema(engine)

        columns = _columns(engine, "declarations")
        assert columns["confidence"]["nullable"] is True
        for added in ("ocr_confidence", "extraction_confidence", "original_ocr_text"):
            assert added in columns

    def test_existing_rows_survive_the_rebuild(self, tmp_path):
        engine = _legacy_database(tmp_path, LEGACY_DECLARATIONS)

        sync_schema(engine)

        with engine.begin() as conn:
            row = conn.exec_driver_sql(
                "SELECT id, field, value, confidence FROM declarations"
            ).fetchall()
        assert row == [("d1", "mrp", "Rs. 45.00", 0.91)]

    def test_a_null_confidence_can_then_be_written(self, tmp_path):
        engine = _legacy_database(tmp_path, LEGACY_DECLARATIONS)

        sync_schema(engine)

        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO declarations (id, scan_id, field, present, status, confidence)"
                " VALUES ('d2', 's1', 'net_quantity', 0, 'illegible', NULL)"
            )

    def test_other_tables_still_point_at_the_rebuilt_one(self, tmp_path):
        """The rename must not drag other tables' foreign keys along with it."""
        engine = _legacy_database(tmp_path, LEGACY_DECLARATIONS)

        sync_schema(engine)

        referenced = {
            fk["referred_table"] for fk in inspect(engine).get_foreign_keys("manual_overrides")
        }
        assert "declarations" in referenced


class TestAddingColumns:
    def test_missing_columns_are_added_without_a_rebuild(self, tmp_path):
        engine = _legacy_database(tmp_path, RELAXED_DECLARATIONS)

        sync_schema(engine)

        columns = _columns(engine, "declarations")
        for added in ("ocr_confidence", "extraction_confidence", "original_ocr_text"):
            assert added in columns
        with engine.begin() as conn:
            assert conn.exec_driver_sql("SELECT count(*) FROM declarations").scalar() == 1


class TestNoDrift:
    def test_a_current_database_is_left_alone(self, tmp_path):
        engine = create_engine(f"sqlite:///{tmp_path / 'current.db'}")
        Base.metadata.create_all(engine)
        before = {table: _columns(engine, table) for table in inspect(engine).get_table_names()}

        sync_schema(engine)

        after = {table: _columns(engine, table) for table in inspect(engine).get_table_names()}
        assert before.keys() == after.keys()
        for table in before:
            assert before[table].keys() == after[table].keys()
