from functools import lru_cache
from threading import Lock

from sqlalchemy import delete, func, select

from app.config import settings
from app.models import Chunk, Runbook
from app.recommendations import invalidate_recommendations

_lock = Lock()


@lru_cache
def embedding_model():
    from fastembed import TextEmbedding

    config = settings()
    config.model_cache.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(model_name=config.model_name, cache_dir=str(config.model_cache),
                         threads=config.embedding_threads, enable_cpu_mem_arena=config.embedding_memory_arena)


def embed(texts: list[str]) -> list[list[float]]:
    with _lock:
        return [row.tolist() for row in embedding_model().embed(texts, batch_size=settings().embedding_batch_size)]


def index_runbook(db, runbook_id: str):
    book = db.get(Runbook, runbook_id)
    if book is None:
        return
    revision = book.revision
    content = f"{book.title}\nЕсли {book.condition}\n" + "\n".join(book.steps)
    parts = [content[start : start + 650] for start in range(0, len(content), 520)]
    vectors = embed(parts)
    book = db.scalar(
        select(Runbook)
        .where(Runbook.id == runbook_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if book is None:
        return
    if book.revision != revision:
        db.commit()
        return
    db.execute(delete(Chunk).where(Chunk.runbook_id == book.id))
    for part, vector in zip(parts, vectors, strict=True):
        db.add(Chunk(runbook_id=book.id, text=part, embedding=vector))
    book.status, book.error = "ready", ""
    invalidate_recommendations(db)
    db.commit()


def search_runbooks(db, query: str, limit: int = 3) -> list[dict]:
    vector = embed([query])[0]
    if db.bind.dialect.name != "postgresql":
        raise RuntimeError("Семантический поиск требует PostgreSQL с pgvector")
    distance = Chunk.embedding.cosine_distance(vector)
    # Keep the best chunk per document before limiting results. A long document
    # must not occupy all candidate positions and hide other relevant runbooks.
    ranked = (
        select(
            Chunk.id.label("chunk_id"),
            distance.label("distance"),
            func.row_number().over(partition_by=Chunk.runbook_id, order_by=distance).label("rank"),
        )
        .join(Runbook, Runbook.id == Chunk.runbook_id)
        .where(Runbook.status == "ready")
        .subquery()
    )
    rows = db.execute(
        select(Chunk, Runbook, ranked.c.distance)
        .join(ranked, ranked.c.chunk_id == Chunk.id)
        .join(Runbook, Runbook.id == Chunk.runbook_id)
        .where(ranked.c.rank == 1)
        .order_by(ranked.c.distance, Runbook.id)
        .limit(limit)
    ).all()
    hits, seen = [], set()
    for chunk, book, dist in rows:
        score = round(max(0.0, 1.0 - float(dist)), 4)
        if score < 0.38 or book.id in seen:
            continue
        seen.add(book.id)
        hits.append(
            dict(
                id=book.id,
                title=book.title,
                condition=book.condition,
                steps=book.steps,
                cautions=book.cautions,
                source=book.source,
                category=book.category,
                similarity=score,
                revision=book.revision,
                excerpt=chunk.text[:400],
            )
        )
        if len(hits) >= limit:
            break
    return hits
