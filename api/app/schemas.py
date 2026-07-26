from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings

_settings = get_settings()


class CreateReportRequest(BaseModel):
    idea: str = Field(min_length=20, max_length=_settings.max_idea_chars)
    target_user: str | None = Field(default=None, max_length=280)


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
