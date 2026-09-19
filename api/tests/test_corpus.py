"""Corpus ingest: embeddings, entity upsert, stats endpoint, NULL-embedding path.

The test database is session-scoped and rows accumulate across tests, so every
test that asserts on `entities` uses its own judge domain, and the stats test
asserts deltas rather than absolutes.
"""

import asyncio
import uuid

import pytest

IDEA = "A scheduling tool for independent piano teachers and their students."


async def _run_report(client, auth: dict, idea: str = IDEA, force: bool = False) -> dict:
    resp = await client.post("/reports", json={"idea": idea, "force": force}, headers=auth)
    assert resp.status_code == 202
    slug = resp.json()["public_slug"]

    deadline = asyncio.get_event_loop().time() + 30
    while asyncio.get_event_loop().time() < deadline:
        body = (await client.get(f"/reports/{slug}")).json()
        if body["status"] in ("succeeded", "failed"):
            return body
        await asyncio.sleep(0.25)
    raise AssertionError("report did not reach a terminal status in time")


def _unique_domain() -> str:
    return f"{uuid.uuid4().hex[:12]}.test"


async def _entity_by_domain(domain: str):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Entity

    async with SessionLocal() as session:
        return await session.scalars(select(Entity).where(Entity.domain == domain))


async def _idea_embedding(report_id: int):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Idea, Report

    async with SessionLocal() as session:
        idea_id = await session.scalar(select(Report.idea_id).where(Report.id == report_id))
        return await session.scalar(select(Idea.embedding).where(Idea.id == idea_id))


async def _chunks(report_id: int):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import ResearchChunk

    async with SessionLocal() as session:
        return (
            await session.scalars(select(ResearchChunk).where(ResearchChunk.report_id == report_id))
        ).all()


def test_normalize_domain():
    from app.corpus import normalize_domain

    assert normalize_domain("https://www.Example.com/pricing?ref=x") == "example.com"
    assert normalize_domain("example.com/path") == "example.com"
    assert normalize_domain("EXAMPLE.COM:443") == "example.com"
    assert normalize_domain("  example.com  ") == "example.com"
    assert normalize_domain("") is None
    assert normalize_domain(None) is None


async def test_ingest_embeds_idea_entities_and_chunks(client, judge, embedder, auth):
    judge.domain = _unique_domain()

    body = await _run_report(client, auth)
    assert body["status"] == "succeeded", body.get("error")

    assert await _idea_embedding(body["id"]) is not None

    entity = (await _entity_by_domain(judge.domain)).one()
    assert entity.name == "Example Corp"
    assert entity.source == "web"
    assert entity.seen_count == 1
    assert entity.embedding is not None
    assert entity.description == "Does roughly this, for a different segment."

    chunks = await _chunks(body["id"])
    assert len(chunks) == 4
    assert all(c.embedding is not None for c in chunks)

    # One batched call for the whole run: 1 idea + 1 entity + 4 chunks.
    assert sum(len(batch) for batch in embedder.batches) == 6


async def test_repeat_sighting_upserts_instead_of_duplicating(client, judge, auth):
    """The domain key is what makes seen_count and last_verified_at meaningful."""
    judge.domain = _unique_domain()

    first = await _run_report(client, auth)
    # Deliberately the same idea again: that is what puts the same company in
    # front of the upsert twice. `force` is the escape hatch the duplicate
    # check exists to leave open.
    second = await _run_report(client, auth, force=True)
    assert first["status"] == second["status"] == "succeeded"

    entities = (await _entity_by_domain(judge.domain)).all()
    assert len(entities) == 1
    assert entities[0].seen_count == 2
    assert entities[0].last_verified_at >= entities[0].first_seen_at


async def test_embedding_failure_still_writes_rows(client, judge, embedder, auth):
    """Best-effort means best-effort: a failed embedder costs vectors, not rows."""
    judge.domain = _unique_domain()
    embedder.fail = True

    body = await _run_report(client, auth)
    assert body["status"] == "succeeded", body.get("error")

    assert await _idea_embedding(body["id"]) is None

    entity = (await _entity_by_domain(judge.domain)).one()
    assert entity.embedding is None

    chunks = await _chunks(body["id"])
    assert len(chunks) == 4
    assert all(c.embedding is None for c in chunks)


async def test_duplicate_domain_within_one_run_dedupes():
    """ON CONFLICT cannot touch the same row twice in one statement."""
    from app.corpus import upsert_entities
    from app.db import SessionLocal

    domain = _unique_domain()
    competitors = [
        {"name": "Dupe", "domain": f"https://www.{domain}/about", "what_they_do": "First."},
        {"name": "Dupe", "domain": domain, "what_they_do": "Second."},
        {"name": "No Domain", "domain": None, "what_they_do": "Inserts plainly."},
    ]

    async with SessionLocal() as session:
        upserted = await upsert_entities(session, competitors, [None, None, None])
        await session.commit()

    assert upserted == 1
    entities = (await _entity_by_domain(domain)).all()
    assert len(entities) == 1
    assert entities[0].seen_count == 1


async def test_corpus_stats_endpoint(client, judge, auth):
    judge.domain = _unique_domain()

    before = (await client.get("/corpus/stats")).json()
    body = await _run_report(client, auth)
    assert body["status"] == "succeeded", body.get("error")
    after = (await client.get("/corpus/stats")).json()

    assert after["ideas"]["total"] == before["ideas"]["total"] + 1
    assert after["ideas"]["embedded"] == before["ideas"]["embedded"] + 1
    assert after["entities"]["total"] == before["entities"]["total"] + 1
    assert after["entities"]["embedded"] == before["entities"]["embedded"] + 1
    assert after["research_chunks"]["total"] == before["research_chunks"]["total"] + 4
    assert after["research_chunks"]["embedded"] == before["research_chunks"]["embedded"] + 4


async def test_wrong_dimension_vectors_degrade_to_null(client, judge, embedder, auth):
    """A model whose vectors don't fit the schema costs vectors, not rows.

    `text-embedding-3-large` returns 3072 dimensions against 1536-wide columns.
    The API call succeeds, so this cannot be caught as an embedding failure —
    without a guard it surfaces at commit and takes the whole run's corpus
    writes down with it.
    """
    judge.domain = _unique_domain()
    embedder.DIM = 3072

    body = await _run_report(client, auth)
    assert body["status"] == "succeeded", body.get("error")

    assert await _idea_embedding(body["id"]) is None

    entity = (await _entity_by_domain(judge.domain)).one()
    assert entity.embedding is None

    chunks = await _chunks(body["id"])
    assert len(chunks) == 4
    assert all(c.embedding is None for c in chunks)


async def test_backfill_keeps_each_vector_with_its_own_description(embedder):
    """Two reports describing one domain differently must not cross vectors.

    The upsert overwrites `description` on every sighting, so whichever pass
    supplies the embedding must be the pass whose description lands with it.
    """
    from sqlalchemy import select

    from app.corpus import backfill_report, entity_embedding_text
    from app.db import SessionLocal
    from app.models import Entity

    domain = _unique_domain()
    first = {"competitors": [{"name": "Co", "domain": domain, "what_they_do": "desc A"}]}
    second = {"competitors": [{"name": "Co", "domain": domain, "what_they_do": "desc B"}]}

    for report in (first, second):
        async with SessionLocal() as session:
            await backfill_report(session, embedder, report=report, idea=None, report_id=None)
            await session.commit()

    async with SessionLocal() as session:
        entity = (await session.scalars(select(Entity).where(Entity.domain == domain))).one()

    expected = embedder._vector(entity_embedding_text(second["competitors"][0]))
    assert entity.description == "desc B"
    assert entity.embedding[0] == pytest.approx(expected[0]), (
        "stored vector was computed from a different description"
    )
