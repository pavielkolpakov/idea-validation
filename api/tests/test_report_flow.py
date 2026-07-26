import asyncio

import pytest

IDEA = "A CRM built specifically for mobile dog grooming businesses."


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


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_create_and_complete_report(client):
    resp = await client.post(
        "/reports",
        json={"idea": IDEA},
        headers={"X-Debug-User": "test"},
    )
    assert resp.status_code == 202

    created = resp.json()
    assert created["status"] == "queued"
    assert len(created["public_slug"]) == 12

    body = await _poll_until_terminal(client, created["public_slug"])

    assert body["status"] == "succeeded", body.get("error")
    assert body["error"] is None
    assert body["score"] == 42
    assert body["report"]["competitors"][0]["domain"] == "example.com"
    assert IDEA[:50] in body["report"]["echo"]


async def test_unknown_slug_is_404(client):
    resp = await client.get("/reports/doesnotexist")
    assert resp.status_code == 404


@pytest.mark.parametrize("idea", ["too short", "x" * 2000])
async def test_idea_length_is_validated(client, idea):
    resp = await client.post("/reports", json={"idea": idea})
    assert resp.status_code == 422
