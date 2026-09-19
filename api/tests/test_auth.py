"""Identity: anonymous ids, verified tokens, and the claim that joins them.

Phase 4 replaces the `X-Debug-User` shim. An anonymous visitor mints a uuid
client-side and sends it as `X-Anon-Id`; the server resolves it to an ordinary
`users` row (`external_id = "anon:<uuid>"`), which is what lets quota, ownership
and the post-signup claim all work without a schema change.
"""

import asyncio
from uuid import uuid4

IDEA = "A CRM built specifically for mobile dog grooming businesses."
OTHER_IDEA = "A marketplace connecting retired welders with apprenticeship programs."

ANON = "11111111-1111-1111-1111-111111111111"
OTHER_ANON = "22222222-2222-2222-2222-222222222222"


async def _poll_until_terminal(client, slug: str, timeout: float = 30.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        body = (await client.get(f"/reports/{slug}")).json()
        if body["status"] in ("succeeded", "failed"):
            return body
        await asyncio.sleep(0.25)
    raise AssertionError("report did not reach a terminal status in time")


async def test_anon_id_determines_who_owns_the_report(client):
    """The free run, and proof the id is load-bearing.

    Asserting only that the POST returns 202 would pass against a server that
    ignores the header entirely — so the test that matters is that the report
    belongs to *that* anonymous visitor and not to a different one.
    """
    resp = await client.post("/reports", json={"idea": IDEA}, headers={"X-Anon-Id": ANON})
    assert resp.status_code == 202
    slug = resp.json()["public_slug"]

    body = await _poll_until_terminal(client, slug)
    assert body["status"] == "succeeded", body.get("error")

    mine = await client.get("/reports", headers={"X-Anon-Id": ANON})
    assert mine.status_code == 200
    assert [r["public_slug"] for r in mine.json()] == [slug]

    someone_else = await client.get("/reports", headers={"X-Anon-Id": OTHER_ANON})
    assert someone_else.json() == []


async def test_bearer_token_identifies_the_user(client, verifier):
    """A verified token's `sub` is the identity, not the raw token string."""
    verifier.tokens = {"tok-a": "user_aaa", "tok-b": "user_bbb"}

    resp = await client.post(
        "/reports", json={"idea": IDEA}, headers={"Authorization": "Bearer tok-a"}
    )
    assert resp.status_code == 202
    slug = resp.json()["public_slug"]
    await _poll_until_terminal(client, slug)

    mine = await client.get("/reports", headers={"Authorization": "Bearer tok-a"})
    assert [r["public_slug"] for r in mine.json()] == [slug]

    other = await client.get("/reports", headers={"Authorization": "Bearer tok-b"})
    assert other.json() == []


async def test_request_without_credentials_is_rejected(client):
    """No token, no anon id — there is no implicit identity any more."""
    resp = await client.post("/reports", json={"idea": IDEA})
    assert resp.status_code == 401


async def test_unverifiable_token_is_rejected(client, verifier):
    """A token the verifier does not recognise must not fall through to anything."""
    resp = await client.post(
        "/reports", json={"idea": IDEA}, headers={"Authorization": "Bearer forged"}
    )
    assert resp.status_code == 401


async def test_anonymous_visitor_gets_exactly_one_free_run(client):
    """The free run is free once. The second one is the sign-in wall."""
    anon = {"X-Anon-Id": str(uuid4())}

    first = await client.post("/reports", json={"idea": IDEA}, headers=anon)
    assert first.status_code == 202
    await _poll_until_terminal(client, first.json()["public_slug"])

    second = await client.post("/reports", json={"idea": OTHER_IDEA}, headers=anon)
    assert second.status_code == 429
    assert second.json()["reason"] == "anon_quota"


async def test_signed_in_user_is_not_held_to_the_anonymous_limit(client, auth):
    """Signing in is what the wall is for; it must actually lift it."""
    for idea in (IDEA, OTHER_IDEA):
        resp = await client.post("/reports", json={"idea": idea}, headers=auth)
        assert resp.status_code == 202, resp.text
        await _poll_until_terminal(client, resp.json()["public_slug"])


async def test_signed_in_user_is_capped_at_the_monthly_limit(client, auth):
    """The account quota is the real ceiling, and it reports a distinct reason."""
    from app.config import get_settings

    limit = get_settings().monthly_free_runs
    for i in range(limit):
        resp = await client.post(
            "/reports",
            json={"idea": f"A niche scheduling tool for trade number {i} in rural areas."},
            headers=auth,
        )
        assert resp.status_code == 202, resp.text
        await _poll_until_terminal(client, resp.json()["public_slug"])

    over = await client.post(
        "/reports",
        json={"idea": "One idea past the limit, which should not be researched."},
        headers=auth,
    )
    assert over.status_code == 429
    assert over.json()["reason"] == "user_quota"


async def test_failed_run_refunds_the_credit(client, research_client):
    """Research is fail-soft, so a `failed` run is almost always our fault.

    Charging for it produces the worst support conversation there is: the run
    broke *and* it took the user's last credit. The anonymous limit of one makes
    the refund observable in a single run.
    """
    anon = {"X-Anon-Id": str(uuid4())}
    research_client.fail_agents = {"competitors", "incumbents", "market_signals", "graveyard"}

    first = await client.post("/reports", json={"idea": IDEA}, headers=anon)
    assert first.status_code == 202
    body = await _poll_until_terminal(client, first.json()["public_slug"])
    assert body["status"] == "failed"

    research_client.fail_agents = set()
    second = await client.post("/reports", json={"idea": OTHER_IDEA}, headers=anon)
    assert second.status_code == 202, second.text


async def test_claim_moves_the_anonymous_report_to_the_new_account(client, auth):
    """Signing up must not be the moment the report disappears."""
    anon_id = str(uuid4())
    anon = {"X-Anon-Id": anon_id}

    resp = await client.post("/reports", json={"idea": IDEA}, headers=anon)
    slug = resp.json()["public_slug"]
    await _poll_until_terminal(client, slug)

    assert (await client.get("/reports", headers=auth)).json() == []

    claimed = await client.post("/auth/claim", headers={**auth, "X-Anon-Id": anon_id})
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["claimed"] == 1

    mine = await client.get("/reports", headers=auth)
    assert [r["public_slug"] for r in mine.json()] == [slug]
    assert (await client.get("/reports", headers=anon)).json() == []


async def test_an_anonymous_caller_cannot_claim(client):
    """Claiming requires an account to claim *into*.

    The anon id is both the caller's identity and the thing being claimed, so a
    tokenless claim is either a no-op or a way to move reports between anonymous
    ids using nothing but a guessed uuid. Neither is worth allowing.
    """
    victim_id = str(uuid4())
    resp = await client.post("/reports", json={"idea": IDEA}, headers={"X-Anon-Id": victim_id})
    await _poll_until_terminal(client, resp.json()["public_slug"])

    stolen = await client.post("/auth/claim", headers={"X-Anon-Id": victim_id})
    assert stolen.status_code == 403

    still_theirs = await client.get("/reports", headers={"X-Anon-Id": victim_id})
    assert len(still_theirs.json()) == 1


async def test_resubmitting_the_same_idea_offers_the_existing_report(client, auth):
    """A double-submit should not cost a credit and an Opus call for a report
    the user already has — but re-running deliberately stays possible."""
    first = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    slug = first.json()["public_slug"]
    await _poll_until_terminal(client, slug)

    again = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    assert again.status_code == 409
    assert again.json()["existing_slug"] == slug

    forced = await client.post("/reports", json={"idea": IDEA, "force": True}, headers=auth)
    assert forced.status_code == 202, forced.text
    assert forced.json()["public_slug"] != slug


async def test_a_different_user_pitching_the_same_idea_still_gets_a_run(client, auth, verifier):
    """Dedupe is per-user on purpose.

    Global dedupe would serve the first founder's report to the second, and
    destroy the "N people pitched this" signal `ideas` exists to capture.
    """
    first = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    await _poll_until_terminal(client, first.json()["public_slug"])

    verifier.tokens["tok-second"] = "user_second"
    second = await client.post(
        "/reports", json={"idea": IDEA}, headers={"Authorization": "Bearer tok-second"}
    )
    assert second.status_code == 202, second.text
    assert second.json()["public_slug"] != first.json()["public_slug"]


async def test_anonymous_runs_are_capped_per_ip(client):
    """The anon id is a dedupe key, not a ceiling — it is forgeable by `curl`.

    Without an IP cap, a one-line loop minting a fresh uuid per request gets
    unlimited Opus calls.
    """
    from app.config import get_settings

    allowed = get_settings().anon_runs_per_ip
    for i in range(allowed):
        resp = await client.post(
            "/reports",
            json={"idea": f"A tool for tracking artisanal cheese inventory, take {i}."},
            headers={"X-Anon-Id": str(uuid4())},
        )
        assert resp.status_code == 202, resp.text
        await _poll_until_terminal(client, resp.json()["public_slug"])

    blocked = await client.post(
        "/reports",
        json={"idea": "One more idea from the same address, which should not run."},
        headers={"X-Anon-Id": str(uuid4())},
    )
    assert blocked.status_code == 429
    assert blocked.json()["reason"] == "ip_rate"


async def test_concurrent_identical_submissions_produce_one_run(client, auth):
    """A double-clicked submit must not buy two identical reports.

    The duplicate check and the insert have to be serialized per (user, idea):
    otherwise both requests read "no duplicate", both consume a credit, and both
    launch a full research run.
    """
    first, second = await asyncio.gather(
        client.post("/reports", json={"idea": IDEA}, headers=auth),
        client.post("/reports", json={"idea": IDEA}, headers=auth),
    )
    assert sorted([first.status_code, second.status_code]) == [202, 409]

    mine = await client.get("/reports", headers=auth)
    assert len(mine.json()) == 1


async def test_claiming_an_in_flight_report_does_not_misdirect_its_refund(
    client, auth, research_client
):
    """The refund must go back to whoever was charged.

    A claim rewrites `reports.user_id` while the run is still going. If the
    refund resolves the owner at failure time, it credits the signed-in account
    and leaves the anonymous visitor's one free run permanently spent.
    """
    anon_id = str(uuid4())
    anon = {"X-Anon-Id": anon_id}
    research_client.fail_agents = {"competitors", "incumbents", "market_signals", "graveyard"}
    # Keep the run alive long enough to claim it mid-flight.
    research_client.delays = dict.fromkeys(research_client.fail_agents, 0.3)

    post = asyncio.create_task(client.post("/reports", json={"idea": IDEA}, headers=anon))
    await asyncio.sleep(0.15)

    claimed = await client.post("/auth/claim", headers={**auth, "X-Anon-Id": anon_id})
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["claimed"] == 1

    resp = await post
    body = await _poll_until_terminal(client, resp.json()["public_slug"])
    assert body["status"] == "failed"

    research_client.fail_agents = set()
    research_client.delays = {}
    again = await client.post("/reports", json={"idea": OTHER_IDEA}, headers=anon)
    assert again.status_code == 202, again.text
