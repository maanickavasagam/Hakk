from __future__ import annotations

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.schema import CreateColumn

from .config import DATABASE_URL

log = logging.getLogger("hakk.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _literal_default(column) -> str | None:
    """SQL literal for a column's plain Python-side default, or None if there
    isn't one simple enough to express as one.

    `mapped_column(Boolean, default=False)` only tells SQLAlchemy's *ORM* what
    to insert — it does not become a SQL-level DEFAULT on the column, because
    CREATE TABLE never needs one (a brand new table has no existing rows to
    backfill). ALTER TABLE ADD COLUMN is a different story: SQLite refuses to
    add a NOT NULL column with nothing to put in the existing rows. So this
    exists purely to give the ALTER statement a DEFAULT that CREATE TABLE was
    always fine without.
    """
    default = column.default
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


def _add_missing_columns() -> None:
    """Additive-only schema catch-up for databases created by an earlier build.

    create_all() creates missing *tables* but never alters existing ones, so a
    column added to a model after someone already has a hakk.db would blow up on
    the first query. This adds those columns rather than requiring the file be
    deleted. It is deliberately additive only — no drops, no type changes; a
    change that needs either of those wants a real migration tool.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present or column.primary_key:
                    continue
                ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                if not column.nullable:
                    literal = _literal_default(column)
                    if literal is not None:
                        ddl += f" DEFAULT {literal}"
                connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))
                log.info("added missing column %s.%s", table.name, column.name)


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
