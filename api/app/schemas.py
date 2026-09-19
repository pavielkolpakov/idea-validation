from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import get_settings

_settings = get_settings()


class CreateReportRequest(BaseModel):
    idea: str = Field(min_length=20, max_length=_settings.max_idea_chars)
    target_user: str | None = Field(default=None, max_length=280)
    # Re-running an idea months later to see what changed is a real use of this
    # product, so the duplicate check offers rather than forbids.
    force: bool = False


# Mirrors models.REPORT_STATUSES. A Literal rather than `str` so the generated
# client gets an exhaustive union instead of `string` — the frontend branches on
# this to decide whether to keep streaming.
ReportStatus = Literal["queued", "running", "succeeded", "failed"]


class CreateReportResponse(BaseModel):
    id: int
    public_slug: str
    status: ReportStatus


class QuotaError(BaseModel):
    """Why a submission was turned away without spending anything.

    `reason` is a closed set so the client's branch is exhaustive rather than
    guessed: these three mean genuinely different things to a user — "sign in
    to keep going", "you are out of runs this month", and "too many free runs
    from this address".
    """

    reason: Literal["anon_quota", "user_quota", "ip_rate"]


class DuplicateError(BaseModel):
    """You already ran this. Carries the slug so the UI can link to it."""

    reason: Literal["duplicate"] = "duplicate"
    existing_slug: str


class SubscoresBody(BaseModel):
    """Serialization copy of `Subscores`. No `ge`/`le` — see `ReportBody`."""

    market_size: int = 0
    novelty: int = 0
    competitive_headroom: int = 0
    feasibility: int = 0
    timing: int = 0


class CompetitorBody(BaseModel):
    name: str = ""
    domain: str | None = None
    what_they_do: str = ""
    funding_stage: str | None = None
    sources: list[int] = Field(default_factory=list)


class CitedTextBody(BaseModel):
    """Serialization copy of both `Risk` and `DifferentiationAngle`."""

    text: str = ""
    sources: list[int] = Field(default_factory=list)


class ReportBody(BaseModel):
    """What a stored report looks like on the way out.

    Deliberately *not* `graph.schema.JudgeReport`, even though it mirrors it
    field for field. `JudgeReport` is a **generation** contract: strict on
    purpose (`risks` needs at least one entry, the verdict must be substantive)
    so a bad judge output fails the run rather than shipping. This is a
    **serialization** contract over rows that are already in the database.

    Reuse the strict model here and any row written under older rules — a
    pre-rename `competitive_intensity`, a report with zero risks — turns a
    `GET` into a 500. The user's own paid-for report becomes unservable because
    of a rule that exists to police the LLM. Hence: same shape, no constraints,
    every list defaulting empty.

    `tests/test_api_contract.py` asserts the field sets stay in step.
    """

    verdict: str = ""
    subscores: SubscoresBody = Field(default_factory=SubscoresBody)
    competitors: list[CompetitorBody] = Field(default_factory=list)
    risks: list[CitedTextBody] = Field(default_factory=list)
    differentiation: list[CitedTextBody] = Field(default_factory=list)

    # Added by the judge node on top of `JudgeReport`.
    degraded_agents: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)

    @field_validator("risks", "differentiation", mode="before")
    @classmethod
    def _lift_legacy_strings(cls, value: object) -> object:
        """Phase 1 wrote these as plain strings, before citations existed.

        Tolerating old rows is this model's whole job, and "the field exists
        but held a different type" is the most common way a stored shape
        changes — dropping those rows to a 500 would defeat the point. The
        string becomes the `text`, with no sources, which is exactly what it
        meant at the time.
        """
        if isinstance(value, list):
            return [{"text": v, "sources": []} if isinstance(v, str) else v for v in value]
        return value


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_slug: str
    status: ReportStatus
    step: str | None
    error: str | None
    score: int | None
    report: ReportBody | None
    created_at: datetime
    updated_at: datetime


class ReportSummary(BaseModel):
    """History row. Deliberately not the full report: the body is tens of KB."""

    public_slug: str
    status: ReportStatus
    score: int | None
    idea: str
    created_at: datetime
