"""Corpus ingest: embeddings, entity upsert, stats endpoint, NULL-embedding path.

The test database is session-scoped and rows accumulate across tests, so every
test that asserts on `entities` uses its own judge domain, and the stats test
asserts deltas rather than absolutes.
"""

import asyncio
import uuid

IDEA = "A scheduling tool for independent piano teachers and their students."


async def _run_report(client, idea: str = IDEA) -> dict:
    resp = await client.post("/reports", json={"idea": idea}, headers={"X-Debug-User": "test"})
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


async def test_ingest_embeds_idea_entities_and_chunks(client, judge, embedder):
    judge.domain = _unique_domain()

    body = await _run_report(client)
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


async def test_repeat_sighting_upserts_instead_of_duplicating(client, judge):
    """The domain key is what makes seen_count and last_verified_at meaningful."""
    judge.domain = _unique_domain()

    first = await _run_report(client)
    second = await _run_report(client)
    assert first["status"] == second["status"] == "succeeded"

    entities = (await _entity_by_domain(judge.domain)).all()
    assert len(entities) == 1
    assert entities[0].seen_count == 2
    assert entities[0].last_verified_at >= entities[0].first_seen_at


async def test_embedding_failure_still_writes_rows(client, judge, embedder):
    """Best-effort means best-effort: a failed embedder costs vectors, not rows."""
    judge.domain = _unique_domain()
    embedder.fail = True

    body = await _run_report(client)
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


async def test_corpus_stats_endpoint(client, judge):
    judge.domain = _unique_domain()

    before = (await client.get("/corpus/stats")).json()
    body = await _run_report(client)
    assert body["status"] == "succeeded", body.get("error")
    after = (await client.get("/corpus/stats")).json()

    assert after["ideas"]["total"] == before["ideas"]["total"] + 1
    assert after["ideas"]["embedded"] == before["ideas"]["embedded"] + 1
    assert after["entities"]["total"] == before["entities"]["total"] + 1
    assert after["entities"]["embedded"] == before["entities"]["embedded"] + 1
    assert after["research_chunks"]["total"] == before["research_chunks"]["total"] + 4
    assert after["research_chunks"]["embedded"] == before["research_chunks"]["embedded"] + 4


async def test_backfill_skips_entities_that_are_already_embedded(embedder):
    """The upsert coalesces a redundant vector away, so don't pay for one."""
    from app.corpus import embed_missing_entities, upsert_entities
    from app.db import SessionLocal

    embedded, missing, plain = _unique_domain(), _unique_domain(), None
    async with SessionLocal() as session:
        await upsert_entities(
            session,
            [
                {"name": "Has Vector", "domain": embedded, "what_they_do": "Already embedded."},
                {"name": "No Vector", "domain": missing, "what_they_do": "Embedding is NULL."},
            ],
            [[0.5] * embedder.DIM, None],
        )
        await session.commit()

    competitors = [
        {"name": "Has Vector", "domain": f"https://www.{embedded}/x", "what_they_do": "Same co."},
        {"name": "No Vector", "domain": missing, "what_they_do": "Same co."},
        {"name": "Domainless", "domain": plain, "what_they_do": "Plain insert."},
    ]
    async with SessionLocal() as session:
        vectors = await embed_missing_entities(session, embedder, competitors)

    assert vectors[0] is None
    assert vectors[1] is not None and vectors[2] is not None
    # Only the two that need a vector were sent to the embedder.
    assert [len(b) for b in embedder.batches] == [2]
