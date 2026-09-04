import secrets
import string
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import get_db
from app.models import Idea, Report
from app.runner import run_report
from app.schemas import CreateReportRequest, CreateReportResponse, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

_ALPHABET = string.ascii_lowercase + string.digits


def make_slug(length: int = 12) -> str:
    """Opaque public identifier. Keeps sequential ids out of share URLs, which
    would otherwise leak total volume to anyone who can count."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=CreateReportResponse)
async def create_report(
    payload: CreateReportRequest,
    background: BackgroundTasks,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateReportResponse:
    idea = Idea(text=payload.idea, target_user=payload.target_user)
    db.add(idea)
    await db.flush()

    report = Report(
        public_slug=make_slug(),
        user_id=user.id,
        idea_id=idea.id,
        status="queued",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    background.add_task(run_report, report.id, idea.id, payload.idea, payload.target_user)

    return CreateReportResponse(id=report.id, public_slug=report.public_slug, status=report.status)


@router.get("/{public_slug}", response_model=ReportResponse)
async def get_report(
    public_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Report:
    report = await db.scalar(select(Report).where(Report.public_slug == public_slug))
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report
