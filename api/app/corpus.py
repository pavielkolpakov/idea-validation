"""Corpus ingest: embed and write ideas, entities, and research chunks.

Runs from the runner, after the report row is committed — never from a graph
node (nodes never touch the database; see app/graph/CLAUDE.md). Everything here
is best-effort: the caller wraps `ingest_run` in a try/except, and an embedding
failure degrades to NULL embeddings with the rows still written. A corpus
failure must never cost the user their report.

Entities are the asset. They are read straight off the judge's competitor table
(no separate extraction call — a second list could only disagree with the
report) and upserted on normalized domain, which is what makes `seen_count`
and `last_verified_at` meaningful when retrieval turns on.
"""

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embeddings import EmbeddingClient
from app.models import Entity, Idea, ResearchChunk

log = logging.getLogger(__name__)


def normalize_domain(raw: str | None) -> str | None:
    """Strip scheme/www/path/port, lowercase. The entity dedup key.

    Done on write, deliberately not at query time: merging near-duplicates by
    embedding similarity is a later, retrieval-side concern — the domain key
    handles the common case.
    """
    if not raw or not raw.strip():
        return None
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split("?")[0].split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d or None


async def _embed(embedder: EmbeddingClient | None, texts: list[str]) -> list[list[float] | None]:
    """One batched call for the whole run; failure degrades to NULLs, not lost rows."""
    if embedder is None or not texts:
        return [None] * len(texts)
    try:
        return await embedder.embed(texts)
    except Exception:  # noqa: BLE001 — best-effort; rows are still written
        log.exception("embedding failed; writing corpus rows with NULL embeddings")
        return [None] * len(texts)


async def upsert_entities(
    session: AsyncSession,
    competitors: list[dict],
    embeddings: list[list[float] | None],
) -> int:
    """Upsert judge competitors into `entities`, keyed on normalized domain.

    Dedupes within the batch first: Postgres `ON CONFLICT` cannot touch the same
    row twice in one statement, and the judge can mention a company in both the
    competitors and incumbents dossiers. Domain-less competitors are plain
    inserts (multiple NULLs are legal under the unique constraint) — they have
    no dedup story until embedding-similarity merge exists.
    """
    by_domain: dict[str, tuple[dict, list[float] | None]] = {}
    for comp, vec in zip(competitors, embeddings, strict=True):
        domain = normalize_domain(comp.get("domain"))
        if domain is None:
            session.add(_entity_row(comp, None, vec))
        elif domain not in by_domain:
            by_domain[domain] = (comp, vec)

    if not by_domain:
        return 0

    stmt = pg_insert(Entity).values(
        [
            {
                "name": comp.get("name") or domain,
                "domain": domain,
                "description": comp.get("what_they_do"),
                "funding_stage": comp.get("funding_stage"),
                "embedding": vec,
                "source": "web",
            }
            for domain, (comp, vec) in by_domain.items()
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["domain"],
        set_={
            "name": stmt.excluded.name,
            # A repeat sighting refreshes the record but never erases what a
            # previous run knew: only overwrite when the new value exists.
            "description": func.coalesce(stmt.excluded.description, Entity.description),
            "funding_stage": func.coalesce(stmt.excluded.funding_stage, Entity.funding_stage),
            "embedding": func.coalesce(stmt.excluded.embedding, Entity.embedding),
            "seen_count": Entity.seen_count + 1,
            "last_verified_at": func.now(),
        },
    )
    await session.execute(stmt)
    return len(by_domain)


def _entity_row(comp: dict, domain: str | None, vec: list[float] | None) -> Entity:
    return Entity(
        name=comp.get("name") or domain or "unknown",
        domain=domain,
        description=comp.get("what_they_do"),
        funding_stage=comp.get("funding_stage"),
        embedding=vec,
        source="web",
    )


def entity_embedding_text(comp: dict) -> str:
    """What an entity's embedding is computed from, per PLAN.md: name + description."""
    return f"{comp.get('name')}: {comp.get('what_they_do')}"


async def ingest_run(
    session: AsyncSession,
    embedder: EmbeddingClient | None,
    *,
    report_id: int,
    idea_id: int,
    idea_text: str,
    dossiers: list[dict],
    report: dict | None,
) -> None:
    """Embed and persist everything one run contributes to the corpus.

    One session, one batched embedding call, one commit. Runs after the report
    row is committed, so nothing here can block or lose the report itself.
    """
    competitors = (report or {}).get("competitors") or []
    chunk_dossiers = [d for d in dossiers if (d.get("text") or "").strip()]

    # What gets embedded, per PLAN.md: the idea text, name+description per
    # entity, and each chunk's text.
    texts = [idea_text]
    texts += [entity_embedding_text(c) for c in competitors]
    texts += [d["text"] for d in chunk_dossiers]
    vectors = await _embed(embedder, texts)

    idea_vec, rest = vectors[0], vectors[1:]
    entity_vecs, chunk_vecs = rest[: len(competitors)], rest[len(competitors) :]

    idea = await session.get(Idea, idea_id)
    if idea is not None and idea.embedding is None:
        idea.embedding = idea_vec

    await upsert_entities(session, competitors, entity_vecs)

    for dossier, vec in zip(chunk_dossiers, chunk_vecs, strict=True):
        session.add(
            ResearchChunk(
                report_id=report_id,
                agent=dossier["agent"],
                text=dossier["text"],
                citations=dossier.get("citations") or [],
                embedding=vec,
                source="web",
            )
        )

    await session.commit()
    log.info(
        "ingested report %s: %d entities, %d chunks (embedded: %s)",
        report_id,
        len(competitors),
        len(chunk_dossiers),
        any(v is not None for v in vectors),
    )


async def embed_missing_idea(embedder: EmbeddingClient, idea: Idea) -> None:
    """Backfill helper: embed one idea row in place. Caller commits."""
    [vec] = await embedder.embed([idea.text])
    idea.embedding = vec


async def embed_missing_entities(
    session: AsyncSession, embedder: EmbeddingClient, competitors: list[dict]
) -> list[list[float] | None]:
    """Backfill helper: vectors for `upsert_entities`, embedding only what needs it.

    The upsert coalesces a new embedding away when the row already has one, so
    embedding an already-embedded entity is spend for a discarded result. Returns
    a vector per competitor, `None` where the existing row already has one.
    Domain-less competitors are always embedded — they are plain inserts.
    """
    domains = {normalize_domain(c.get("domain")) for c in competitors} - {None}
    embedded: set[str] = set()
    if domains:
        embedded = set(
            (
                await session.scalars(
                    select(Entity.domain).where(
                        Entity.domain.in_(domains), Entity.embedding.is_not(None)
                    )
                )
            ).all()
        )

    stale = [
        i for i, c in enumerate(competitors) if normalize_domain(c.get("domain")) not in embedded
    ]
    vectors: list[list[float] | None] = [None] * len(competitors)
    if stale:
        computed = await embedder.embed([entity_embedding_text(competitors[i]) for i in stale])
        for i, vec in zip(stale, computed, strict=True):
            vectors[i] = vec
    return vectors


async def chunks_missing_embeddings(
    session: AsyncSession, embedder: EmbeddingClient, report_id: int
) -> int:
    """Backfill helper: embed a report's NULL-embedding chunks. Caller commits."""
    chunks = (
        await session.scalars(
            select(ResearchChunk).where(
                ResearchChunk.report_id == report_id, ResearchChunk.embedding.is_(None)
            )
        )
    ).all()
    if not chunks:
        return 0
    vectors = await embedder.embed([c.text for c in chunks])
    for chunk, vec in zip(chunks, vectors, strict=True):
        chunk.embedding = vec
    return len(chunks)
