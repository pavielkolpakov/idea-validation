"""Live end-to-end run against the real Perplexity and Anthropic APIs.

Deselected by default (`make test` runs `-m "not live"`); run with `make test-live`.

**This is what stops the fakes from lying.** Everything in `test_report_flow.py`
asserts against `FakeResearchClient`, whose citation shape is an assumption about
what `ChatPerplexity` returns. `extract_citations` has never been checked against
a real response. When Perplexity or the LangChain wrapper changes that shape,
this suite is the only thing that will notice — treat a failure here as the
contract having moved, not as flakiness.
"""

import asyncio

import pytest

pytestmark = pytest.mark.live

IDEA = "A CRM built specifically for mobile dog grooming businesses."


@pytest.fixture
def live_client(test_database):
    """Same app, real clients. Deliberately does not monkeypatch build_clients.

    Keys must be read through `Settings`, not `os.environ`: pydantic-settings
    loads `api/.env` directly and never exports into the process environment, so
    an `os.environ` check silently skips this suite even when the keys are set.
    """
    from app.config import get_settings

    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("PERPLEXITY_API_KEY", settings.perplexity_api_key),
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        )
        if not value.strip()
    ]
    if missing:
        pytest.skip(f"not set in api/.env: {', '.join(missing)}")
    return None


async def test_real_pipeline_produces_a_usable_report(live_client, test_database):
    import httpx

    from app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=600) as c:
            resp = await c.post("/reports", json={"idea": IDEA}, headers={"X-Debug-User": "live"})
            assert resp.status_code == 202
            slug = resp.json()["public_slug"]

            deadline = asyncio.get_event_loop().time() + 300
            while asyncio.get_event_loop().time() < deadline:
                body = (await c.get(f"/reports/{slug}")).json()
                if body["status"] in ("succeeded", "failed"):
                    break
                await asyncio.sleep(2)
            else:
                raise AssertionError("live run did not finish within 300s")

    assert body["status"] == "succeeded", body.get("error")
    report = body["report"]

    # No agent should have degraded on a healthy run — if one did, the failure
    # is real and worth reading, not worth asserting around.
    assert report["degraded_agents"] == [], report["degraded_agents"]

    assert 0 <= body["score"] <= 100
    assert len(report["verdict"]) > 100, "verdict is too thin to be useful"
    assert report["competitors"], "no competitors found for a well-populated market"

    # The contract this suite exists to pin: real citations came back, and every
    # index the judge emitted resolves into that table.
    citations = report["citations"]
    assert citations, "no citations extracted — extract_citations may be stale"
    assert all(u.startswith("http") for u in citations)

    cited = [i for c in report["competitors"] for i in c["sources"]]
    assert all(0 <= i < len(citations) for i in cited)
