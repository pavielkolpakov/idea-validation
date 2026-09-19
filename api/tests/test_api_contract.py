"""The OpenAPI surface the frontend is generated from.

Codegen is only as good as the spec. `report` was typed `dict`, which generates
`Record<string, unknown>` — exactly the hand-written type it was supposed to
replace — so these tests assert the spec actually describes the payload.
"""

IDEA = "A CRM built specifically for mobile dog grooming businesses."


async def test_openapi_describes_the_report_body(client):
    spec = (await client.get("/openapi.json")).json()

    body = spec["components"]["schemas"]["ReportBody"]["properties"]
    assert {
        "verdict",
        "subscores",
        "competitors",
        "risks",
        "differentiation",
        "degraded_agents",
        "citations",
    } <= set(body)

    competitor = spec["components"]["schemas"]["CompetitorBody"]["properties"]
    assert {"name", "domain", "what_they_do", "sources"} <= set(competitor)


async def test_a_report_written_under_older_rules_still_serves(client, auth):
    """The reason `ReportBody` is not `JudgeReport`.

    `JudgeReport` requires at least one risk and a substantive verdict — rules
    that police the LLM at generation time. Applying them on the way *out*
    makes a row written under older rules unservable, so the user's paid-for
    report 500s because of a constraint that has nothing to do with reading it.
    """
    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import Report

    resp = await client.post("/reports", json={"idea": IDEA}, headers=auth)
    slug = resp.json()["public_slug"]
    report_id = resp.json()["id"]

    legacy = {
        "verdict": "too short",  # JudgeReport requires >= 20 chars
        "subscores": {"market_size": 150},  # out of the 0-100 range it enforces
        "risks": [],  # JudgeReport requires at least one
        "competitive_intensity": 40,  # a field that no longer exists
    }
    async with SessionLocal() as session:
        await session.execute(update(Report).where(Report.id == report_id).values(report=legacy))
        await session.commit()

    body = (await client.get(f"/reports/{slug}")).json()
    assert body["report"]["verdict"] == "too short"
    assert body["report"]["subscores"]["market_size"] == 150
    assert body["report"]["risks"] == []
    # Fields that fell out of the schema are dropped, not fatal.
    assert body["report"]["differentiation"] == []


def test_the_serialization_models_track_the_generation_models():
    """Two hand-written copies of one shape drift. This is the tripwire."""
    from app.graph.schema import Competitor, JudgeReport, Subscores
    from app.schemas import CompetitorBody, ReportBody, SubscoresBody

    for strict, tolerant in (
        (JudgeReport, ReportBody),
        (Subscores, SubscoresBody),
        (Competitor, CompetitorBody),
    ):
        missing = set(strict.model_fields) - set(tolerant.model_fields)
        assert not missing, f"{tolerant.__name__} is missing {missing} from {strict.__name__}"


async def test_openapi_documents_the_submission_gates(client):
    """The gates are the most product-critical branches in the UI.

    The frontend has to tell "sign in to keep going" from "you're out of runs
    this month" from "you already ran this" — all of which arrive as non-2xx.
    Undocumented, that branch is stringly-typed guesswork against a contract
    nothing pins down.
    """
    spec = (await client.get("/openapi.json")).json()
    responses = spec["paths"]["/reports"]["post"]["responses"]
    assert {"202", "409", "422", "429"} <= set(responses)

    quota_ref = responses["429"]["content"]["application/json"]["schema"]["$ref"]
    quota = spec["components"]["schemas"][quota_ref.rsplit("/", 1)[-1]]
    # A closed set, so the client's branch is exhaustive instead of guessed.
    assert set(quota["properties"]["reason"]["enum"]) == {"anon_quota", "user_quota", "ip_rate"}

    dup_ref = responses["409"]["content"]["application/json"]["schema"]["$ref"]
    dup = spec["components"]["schemas"][dup_ref.rsplit("/", 1)[-1]]
    assert "existing_slug" in dup["properties"]


def test_the_status_union_matches_the_database_constraint():
    """`ReportStatus` is what the client branches on; the CHECK is what the
    database allows. A value in one and not the other is a bug in whichever
    ships second."""
    from typing import get_args

    from app.models import REPORT_STATUSES
    from app.schemas import ReportStatus

    assert set(get_args(ReportStatus)) == set(REPORT_STATUSES)
