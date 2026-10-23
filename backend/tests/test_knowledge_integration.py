import os

import pytest
from sqlalchemy import select, text

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("INTEGRATION"), reason="Needs running stack"),
]


def test_real_pgvector_retrieval_and_reindex():
    from app.db import session_factory
    from app.knowledge import index_runbook, search_runbooks
    from app.models import Chunk, Runbook

    with session_factory()() as db:
        assert db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        book = Runbook(
            title="Disk capacity",
            condition="Disk full. На диске сервера закончилось свободное место",
            steps=["Проверить df -h", "Архивировать согласованные логи"],
            category="server",
        )
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


def test_long_document_cannot_hide_another_relevant_runbook():
    from app.db import session_factory
    from app.knowledge import embed, search_runbooks
    from app.models import Chunk, Runbook

    query = "На диске сервера закончилось свободное место"
    vector = embed([query])[0]
    nearby = vector.copy()
    nearby[0] += 0.02
    with session_factory()() as db:
        long = Runbook(title="Long disk guide", condition=query, steps=["Check disk"], status="ready")
        short = Runbook(title="Other disk guide", condition=query, steps=["Check logs"], status="ready")
        db.add_all([long, short])
        db.commit()
        try:
            db.add_all([Chunk(runbook_id=long.id, text=query, embedding=vector) for _ in range(80)])
            db.add(Chunk(runbook_id=short.id, text=query, embedding=nearby))
            db.commit()
            hits = search_runbooks(db, query, 3)
            assert {long.id, short.id}.issubset({hit["id"] for hit in hits})
        finally:
            db.delete(long)
            db.delete(short)
            db.commit()
