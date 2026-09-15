"""Reconciles an existing SQLite file with the current models.

This project has no migration tool (Alembic) — `Base.metadata.create_all()` only
creates tables that don't exist yet, it never alters ones that are already there.
So a database file created before a model change is missing new columns (every query
then raises `no such column: ...`) or still carries an old column constraint (an
insert then raises `NOT NULL constraint failed: ...`). Call `sync_schema()` once at
startup, after `create_all`; it is a no-op on a freshly created database.
"""

from sqlalchemy import Table, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.schema import CreateIndex, CreateTable

from app.database import Base


def _default_literal(default) -> str | None:
    """SQL literal for a mapped_column's Python-side scalar default, if any.

    Only plain scalars are handled (str/int/float/bool) — anything else (callables
    like the `_uuid`/`_now` factories used elsewhere in models.py) is skipped, so
    the new column is simply left NULL for pre-existing rows.
    """
    if default is None or not getattr(default, "is_scalar", False):
        return None
    value = default.arg
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def _add_missing_columns(conn: Connection, engine: Engine, table: Table, existing: set[str]) -> None:
    for column in table.columns:
        if column.name in existing:
            continue
        ddl_type = column.type.compile(dialect=engine.dialect)
        clause = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}'
        literal = _default_literal(column.default)
        if literal is not None:
            clause += f" DEFAULT {literal}"
        conn.execute(text(clause))


def _rebuild_table(conn: Connection, table: Table, existing: set[str]) -> None:
    """Recreate `table` from the model definition, carrying the existing rows over.

    SQLite has no `ALTER COLUMN`, so relaxing a constraint means building the table
    afresh and copying the data across. The original is renamed aside and the real
    table recreated from the model's own `Table` — recreating it under a temporary
    name instead would leave its foreign keys pointing at tables that do not exist
    under that name. `legacy_alter_table` stops the rename rewriting *other* tables'
    foreign-key clauses to follow the temporary name, which would otherwise leave
    them pointing at a table this function is about to drop.
    """
    staged = f"_schema_sync_{table.name}"
    conn.exec_driver_sql("PRAGMA legacy_alter_table=ON")
    try:
        conn.exec_driver_sql(f'ALTER TABLE "{table.name}" RENAME TO "{staged}"')
        conn.execute(CreateTable(table))

        shared = [f'"{c.name}"' for c in table.columns if c.name in existing]
        if shared:
            columns = ", ".join(shared)
            conn.exec_driver_sql(
                f'INSERT INTO "{table.name}" ({columns}) SELECT {columns} FROM "{staged}"'
            )

        conn.exec_driver_sql(f'DROP TABLE "{staged}"')
        for index in table.indexes:
            conn.execute(CreateIndex(index))
    finally:
        conn.exec_driver_sql("PRAGMA legacy_alter_table=OFF")


def _needs_relaxing(table: Table, db_columns: list[dict]) -> bool:
    """True when the file still marks a column NOT NULL that the model now allows to
    be null. The reverse (model stricter than the file) is deliberately left alone:
    existing rows may already hold nulls, so tightening here would fail at startup
    rather than at the one insert that actually violates it.
    """
    model_columns = {c.name: c for c in table.columns}
    for db_column in db_columns:
        model_column = model_columns.get(db_column["name"])
        if model_column is None:
            continue
        if not db_column["nullable"] and model_column.nullable and not model_column.primary_key:
            return True
    return False


def sync_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all() already created this one from scratch, correctly
            db_columns = inspector.get_columns(table.name)
            existing = {c["name"] for c in db_columns}
            if _needs_relaxing(table, db_columns):
                _rebuild_table(conn, table, existing)
            else:
                _add_missing_columns(conn, engine, table, existing)
