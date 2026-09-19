import asyncio

import pytest

IDEA = "A CRM built specifically for mobile dog grooming businesses."

_AGENTS = ("competitors", "incumbents", "market_signals", "graveyard")


async def _poll_until_terminal(client, slug: str, timeout: float = 30.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/reports/{slug}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in ("succeeded", "failed"):
            return body
        await asyncio.sleep(0.25)
    raise AssertionError("report did not reach a terminal status in time")


async def _chunks_for(report_id: int) -> list[dict]:
    """Read corpus rows directly; the stats endpoint only exposes aggregates."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import ResearchChunk

    async with SessionLocal() as session:
        result = await session.scalars(
            select(ResearchChunk).where(ResearchChunk.report_id == report_id)
        )
        return [
            {
                "agent": c.agent,
                "text": c.text,
                "citations": c.citations,
                "source": c.source,
                "embedding": c.embedding,
            }
            for c in result
        ]


async def _dossiers_raw_for(report_id: int) -> dict:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Report

    async with SessionLocal() as session:
        return await session.scalar(select(Report.dossiers_raw).where(Report.id == report_id))


async def _latest_report_step() -> str | None:
    from sqlalchemy import desc, select

    from app.db import SessionLocal
    from app.models import Report

    async with SessionLocal() as session:
        return await session.scalar(select(Report.step).order_by(desc(Report.id)).limit(1))


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_create_and_complete_report(client, research_client, auth):
    resp = await client.post(
        "/reports",
        json={"idea": IDEA},
        headers=auth,
    )
    assert resp.status_code == 202

    created = resp.json()
    assert created["status"] == "queued"
    assert len(created["public_slug"]) == 12

    body = await _poll_until_terminal(client, created["public_slug"])

    assert body["status"] == "succeeded", body.get("error")
    assert body["error"] is None
    assert sorted(research_client.calls) == [
        "competitors",
        "graveyard",
        "incumbents",
        "market_signals",
    ]

    # Weighted mean of the fake judge's subscores, NOT a number the judge chose:
    # 80*.25 + 60*.20 + 40*.20 + 70*.20 + 50*.15 = 61.5 -> 62
    assert body["score"] == 62
    assert body["report"]["competitors"][0]["domain"] == "example.com"
    assert body["report"]["degraded_agents"] == []


async def test_one_failed_agent_still_produces_a_report(client, research_client, auth):
    """A dead researcher costs you a dossier, not the whole run.

    RetryPolicy has already absorbed the transient case by this point, so failing
    hard here would discard three successful Perplexity calls over one that was
    never going to recover.
    """
    research_client.fail_agents = {"graveyard"}

    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])

    assert body["status"] == "succeeded", body.get("error")
    assert body["report"]["degraded_agents"] == ["graveyard"]
    # The surviving three still reached the judge.
    assert body["score"] == 62


async def test_transient_failure_is_retried(client, research_client, auth):
    """A timeout should cost a retry, not a dossier.

    Perplexity timeouts and 429s are the common failure and they recover; the
    degraded path is meant for failures that survive retrying.
    """
    research_client.flaky_agents = {"market_signals": 2}

    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])

    assert body["status"] == "succeeded", body.get("error")
    assert body["report"]["degraded_agents"] == []
    assert research_client.calls.count("market_signals") == 3


async def test_all_agents_failing_fails_the_run(client, research_client, auth):
    """The floor. A report built on nothing isn't degraded, it's not a report."""
    research_client.fail_agents = set(_AGENTS)

    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])

    assert body["status"] == "failed"
    assert body["report"] is None
    assert "all research agents failed" in body["error"]


async def test_out_of_range_citation_fails_the_run(client, judge, auth):
    """The backstop that makes integer citations safe.

    The judge can only emit indices, so it cannot fabricate a URL — but it can
    still emit an index that resolves to nothing. That must fail loudly rather
    than render as a broken source link on a factual claim.
    """
    judge.source_index = 999

    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])

    assert body["status"] == "failed"
    assert "citation" in body["error"]


async def test_citations_are_indices_not_urls(client, judge, auth):
    """The judge is shown a numbered index and never asked for a URL."""
    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])
    assert body["status"] == "succeeded", body.get("error")

    prompt = judge.prompts[0]
    assert "[0] https://example.com/competitors-1" in prompt

    # Indices resolve against the table stored alongside the report.
    citations = body["report"]["citations"]
    assert len(citations) == 8  # 4 agents x 2 URLs each, deduped
    for competitor in body["report"]["competitors"]:
        for i in competitor["sources"]:
            assert citations[i].startswith("https://")


async def test_successful_run_writes_corpus_chunks(client, research_client, auth):
    """Every run feeds the corpus, even though V1 never reads from it."""
    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])
    assert body["status"] == "succeeded", body.get("error")

    # dossiers_raw keeps the unsynthesised research, so a bad judge run can be
    # diagnosed (or re-judged) without re-buying four Perplexity calls.
    raw = await _dossiers_raw_for(body["id"])
    assert sorted(d["agent"] for d in raw["dossiers"]) == sorted(_AGENTS)
    assert all(d["text"] for d in raw["dossiers"])

    rows = await _chunks_for(body["id"])
    assert sorted(r["agent"] for r in rows) == sorted(_AGENTS)
    assert all(r["source"] == "web" for r in rows)
    assert all(r["embedding"] is not None for r in rows)
    assert all(len(r["citations"]) == 2 for r in rows)


async def test_degraded_agent_writes_no_empty_chunk(client, research_client, auth):
    """A failed agent has nothing to contribute; don't pollute the corpus with it."""
    research_client.fail_agents = {"graveyard"}

    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    body = await _poll_until_terminal(client, resp.json()["public_slug"])
    assert body["status"] == "succeeded", body.get("error")

    rows = await _chunks_for(body["id"])
    assert sorted(r["agent"] for r in rows) == ["competitors", "incumbents", "market_signals"]


async def test_progress_never_goes_backwards(client, research_client, auth):
    """Four concurrent researchers must not make progress appear to jump around.

    Each node announcing its own step string would give last-writer-wins: a user
    watching would see the pipeline flicker between agent names in random order.
    The runner aggregates completions into a count instead.
    """
    # Staggered so the four completions are separable by a poller; with equal
    # delays they all land within microseconds and the counter is unobservable.
    research_client.delays = {
        "competitors": 0.10,
        "incumbents": 0.25,
        "market_signals": 0.40,
        "graveyard": 0.55,
    }

    # httpx's ASGITransport awaits BackgroundTasks inside the POST, so the run
    # is already finished by the time the response returns. Poll alongside it.
    post = asyncio.create_task(client.post("/reports", json={"idea": IDEA}, headers=auth))

    seen: list[str] = []
    while not post.done():
        step = await _latest_report_step()
        if step and (not seen or seen[-1] != step):
            seen.append(step)
        await asyncio.sleep(0.01)

    resp = await post
    body = (await client.get(f"/reports/{resp.json()['public_slug']}")).json()
    assert body["status"] == "succeeded", body.get("error")

    counts = [int(s.split("(")[1].split("/")[0]) for s in seen if s.startswith("researching (")]
    assert len(set(counts)) >= 2, f"did not observe progression, saw: {seen}"
    assert counts == sorted(counts), f"progress went backwards: {seen}"


async def test_unknown_slug_is_404(client):
    resp = await client.get("/reports/doesnotexist")
    assert resp.status_code == 404


@pytest.mark.parametrize("idea", ["too short", "x" * 2000])
async def test_idea_length_is_validated(client, idea, auth):
    resp = await client.post("/reports", json={"idea": idea}, headers=auth)
    assert resp.status_code == 422
