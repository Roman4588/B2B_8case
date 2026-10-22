import os

import pytest
from sqlalchemy import select, text

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("INTEGRATION"), reason="Needs running stack")]


def test_real_pgvector_retrieval_and_reindex():
    from app.db import session_factory
    from app.knowledge import index_runbook, search_runbooks
    from app.models import Chunk, Runbook
    with session_factory()() as db:
        assert db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        book = Runbook(title="Disk capacity", condition="Disk full. На диске сервера закончилось свободное место",
                       steps=["Проверить df -h", "Архивировать согласованные логи"], category="server")
        db.add(book)
        db.commit()
        try:
            index_runbook(db, book.id)
            results = search_runbooks(db, "Закончилось место на диске", 3)
            assert any(row["id"] == book.id for row in results)
            first_count = len(db.scalars(select(Chunk).where(Chunk.runbook_id == book.id)).all())
            index_runbook(db, book.id)
            assert len(db.scalars(select(Chunk).where(Chunk.runbook_id == book.id)).all()) == first_count
        finally:
            db.delete(book)
            db.commit()
