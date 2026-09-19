import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import quota
from app.auth import CurrentUser
from app.db import get_db
from app.guardrails import get_precheck
from app.models import Idea, Report
from app.runner import run_report
from app.schemas import (
    CreateReportRequest,
    CreateReportResponse,
    DuplicateError,
    QuotaError,
    ReportResponse,
    ReportSummary,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_ALPHABET = string.ascii_lowercase + string.digits


def make_slug(length: int = 12) -> str:
    """Opaque public identifier. Keeps sequential ids out of share URLs, which
    would otherwise leak total volume to anyone who can count."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


DUPLICATE_WINDOW = timedelta(days=7)


async def _recent_duplicate(db: AsyncSession, user_id: int, idea: str) -> str | None:
    """The caller's own most recent identical idea, if it is still fresh.

    Per-user by design: two founders independently pitching the same idea must
    each get their own run and their own `ideas` row, or the corpus loses the
    "N people pitched this" signal that table exists for.
    """
    return await db.scalar(
        select(Report.public_slug)
        .join(Idea, Report.idea_id == Idea.id)
        # md5() on both sides so the functional index in migration 0002 is used.
        .where(
            Report.user_id == user_id,
            func.md5(Idea.text) == func.md5(idea),
            Report.created_at > datetime.now(UTC) - DUPLICATE_WINDOW,
        )
        .order_by(Report.id.desc())
        .limit(1)
    )


# Declared so codegen types them: the UI branches on these to tell "sign in" from
# "out of runs" from "you already ran this". Bodies are built from the same
# models, so the documented shape and the real one cannot drift.
SUBMISSION_GATES = {
    409: {"model": DuplicateError, "description": "You already ran this idea recently."},
    429: {"model": QuotaError, "description": "Free run used, quota exhausted, or rate limited."},
}


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CreateReportResponse,
    responses=SUBMISSION_GATES,
)
async def create_report(
    payload: CreateReportRequest,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateReportResponse:
    # Coarsest gate first, before a single model call is made.
    if quota.is_anonymous(user) and not await quota.ip_allowed(request):
        return JSONResponse(status_code=429, content=QuotaError(reason="ip_rate").model_dump())

    # Then the free one. The pre-check is a paid call and signed-in callers are
    # exempt from the IP cap, so an exhausted account that is only stopped
    # *after* classification can spend indefinitely by retrying. Advisory read:
    # `consume` below is still the gate that decides.
    if not await quota.has_budget(db, user):
        return JSONResponse(
            status_code=429, content=QuotaError(reason=quota.reason_for(user)).model_dump()
        )

    rejection = await get_precheck().check(payload.idea)
    if rejection:
        raise HTTPException(status_code=422, detail=rejection)

    # Everything from here to the commit is one critical section per (user,
    # idea): the duplicate check, the credit claim, and the insert that makes
    # the duplicate visible to the next request.
    await quota.lock_submission(db, user, payload.idea)

    if not payload.force:
        existing = await _recent_duplicate(db, user.id, payload.idea)
        if existing:
            return JSONResponse(
                status_code=409, content=DuplicateError(existing_slug=existing).model_dump()
            )

    # Claimed before anything is spent, and refunded if the run fails. The
    # charged identity is captured here and carried into the run, because a
    # claim can reassign the report before it finishes.
    charged_user_id, charged_period = user.id, quota.period_for(user)
    if not await quota.consume(db, user):
        return JSONResponse(
            status_code=429, content=QuotaError(reason=quota.reason_for(user)).model_dump()
        )

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

    background.add_task(
        run_report,
        report.id,
        idea.id,
        payload.idea,
        payload.target_user,
        charged_user_id,
        charged_period,
    )

    return CreateReportResponse(id=report.id, public_slug=report.public_slug, status=report.status)


@router.get("", response_model=list[ReportSummary])
async def list_reports(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[ReportSummary]:
    """The caller's own reports, newest first.

    An explicit join rather than a relationship: `models.py` declares none, and
    async SQLAlchemy turns a forgotten eager-load into a runtime error.
    """
    rows = await db.execute(
        select(Report, Idea.text)
        .join(Idea, Report.idea_id == Idea.id)
        .where(Report.user_id == user.id)
        .order_by(Report.id.desc())
        .limit(min(limit, 100))
    )
    return [
        ReportSummary(
            public_slug=report.public_slug,
            status=report.status,
            score=report.score,
            idea=idea_text[:200],
            created_at=report.created_at,
        )
        for report, idea_text in rows
    ]


@router.get("/{public_slug}", response_model=ReportResponse)
async def get_report(
    public_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Report:
    report = await db.scalar(select(Report).where(Report.public_slug == public_slug))
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report
