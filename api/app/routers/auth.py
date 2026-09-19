"""Account endpoints.

`POST /auth/claim` is the one that matters: it moves the reports an anonymous
visitor produced onto the account they just created. Done as an explicit
endpoint rather than a side effect inside `get_current_user`, because one code
path then covers both the brand-new user and the returning one whose provider id
already has a row — the case that breaks "promote the anon row in place".
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import ANON_PREFIX, CurrentUser
from app.db import get_db
from app.models import Report, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/claim")
async def claim_anonymous_reports(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_anon_id: Annotated[str | None, Header()] = None,
) -> dict:
    """Reassign an anonymous visitor's reports to the signed-in caller."""
    if user.external_id is None or user.external_id.startswith(ANON_PREFIX):
        # The anon header is both the caller's identity and the claim target, so
        # a tokenless claim can only shuffle reports between guessed uuids.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="claiming requires a signed-in account",
        )
    if not x_anon_id:
        raise HTTPException(status_code=400, detail="X-Anon-Id header is required")

    anon = await db.scalar(select(User).where(User.external_id == f"{ANON_PREFIX}{x_anon_id}"))
    if anon is None:
        return {"claimed": 0}

    result = await db.execute(
        update(Report).where(Report.user_id == anon.id).values(user_id=user.id)
    )
    await db.commit()
    return {"claimed": result.rowcount}
