from functools import lru_cache
from threading import Lock

from sqlalchemy import delete, select

from app.config import settings
from app.models import Chunk, Runbook

_lock = Lock()


@lru_cache
def embedding_model():
    from fastembed import TextEmbedding
    config = settings()
    config.model_cache.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(model_name=config.model_name, cache_dir=str(config.model_cache), threads=2)


def embed(texts: list[str]) -> list[list[float]]:
    with _lock:
        return [row.tolist() for row in embedding_model().embed(texts, batch_size=16)]


def index_runbook(db, runbook_id: str):
    book = db.get(Runbook, runbook_id)
    if book is None:
        return
    revision = book.revision
    content = f"{book.title}\nЕсли {book.condition}\n" + "\n".join(book.steps)
    parts = [content[start:start + 650] for start in range(0, len(content), 520)]
    vectors = embed(parts)
    db.refresh(book)
    if book.revision != revision:
        return
    db.execute(delete(Chunk).where(Chunk.runbook_id == book.id))
    for part, vector in zip(parts, vectors, strict=True):
        db.add(Chunk(runbook_id=book.id, text=part, embedding=vector))
    book.status, book.error = "ready", ""
    db.commit()


def search_runbooks(db, query: str, limit: int = 3) -> list[dict]:
    vector = embed([query])[0]
    if db.bind.dialect.name != "postgresql":
        raise RuntimeError("Семантический поиск требует PostgreSQL с pgvector")
    distance = Chunk.embedding.cosine_distance(vector)
    rows = db.execute(select(Chunk, Runbook, distance.label("distance"))
                      .join(Runbook, Runbook.id == Chunk.runbook_id)
                      .where(Runbook.status == "ready")
                      .order_by(distance).limit(50)).all()
    hits, seen = [], set()
    for chunk, book, dist in rows:
        score = round(max(0.0, 1.0 - float(dist)), 4)
        if score < 0.38 or book.id in seen:
            continue
        seen.add(book.id)
        hits.append(dict(id=book.id, title=book.title, condition=book.condition, steps=book.steps,
                         cautions=book.cautions, source=book.source, category=book.category,
                         similarity=score, revision=book.revision, excerpt=chunk.text[:400]))
        if len(hits) >= limit:
            break
    return hits
