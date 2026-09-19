from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings

_settings = get_settings()


class CreateReportRequest(BaseModel):
    idea: str = Field(min_length=20, max_length=_settings.max_idea_chars)
    target_user: str | None = Field(default=None, max_length=280)
    # Re-running an idea months later to see what changed is a real use of this
    # product, so the duplicate check offers rather than forbids.
    force: bool = False


class CreateReportResponse(BaseModel):
    id: int
    public_slug: str
    status: str


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_slug: str
    status: str
    step: str | None
    error: str | None
    score: int | None
    report: dict | None
    created_at: datetime
    updated_at: datetime


class ReportSummary(BaseModel):
    """History row. Deliberately not the full report: the body is tens of KB."""

    public_slug: str
    status: str
    score: int | None
    idea: str
    created_at: datetime
