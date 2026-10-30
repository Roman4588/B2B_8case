"""One-time, read-only legacy SQLite import into an otherwise empty database."""
import sqlite3
from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table, create_engine, func, select, text

from app.models import Base

ledger = Table("_deployment_imports", MetaData(), Column("id", String(80), primary_key=True))


def migrate_sqlite(source_path: Path, target_engine) -> dict:
    if not source_path.exists():
        return {"status": "no_legacy_database"}
    ledger.create(target_engine, checkfirst=True)
    marker = "sqlite:" + source_path.name
    source_engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(
        source_path.resolve().as_uri() + "?mode=ro", uri=True))
    try:
        with target_engine.begin() as target:
            if target_engine.dialect.name == "postgresql":
                target.execute(text("SELECT pg_advisory_xact_lock(8010)"))
            if target.scalar(select(ledger.c.id).where(ledger.c.id == marker)):
                return {"status": "already_imported"}
            for table in Base.metadata.sorted_tables:
                if target.scalar(select(func.count()).select_from(table)):
                    raise RuntimeError("Refusing legacy import into a nonempty target database")
            counts = {}
            with source_engine.connect() as source:
                source.exec_driver_sql("BEGIN")
                if source.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
                    raise RuntimeError("Legacy SQLite integrity check failed")
                for table in Base.metadata.sorted_tables:
                    if table.name == "chunks":
                        continue
                    rows = [dict(row) for row in source.execute(select(table)).mappings()]
                    for row in rows:
                        if table.name == "runbooks":
                            row.update(status="queued", error="")
                        elif table.name == "incidents":
                            row.update(recommendations=[], recommendation_status="pending")
                        elif table.name == "import_jobs" and row["status"] == "running":
                            row.update(status="queued", progress=0, error="")
                    if rows:
                        target.execute(table.insert(), rows)
                    counts[table.name] = len(rows)
                target.execute(ledger.insert(), {"id": marker})
            return {"status": "imported", "counts": counts}
    finally:
        source_engine.dispose()
