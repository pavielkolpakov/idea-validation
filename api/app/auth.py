"""Placeholder identity.

Phase 1 has no auth provider (deliberately deferred — the choice leaks into the
schema and nothing in Phases 1-3 needs a real user). Dev sends `X-Debug-User`
and we get-or-create a row. Phase 4 replaces this module wholesale; the
`users.external_id` column is provider-agnostic so no migration is needed.
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User

DEFAULT_DEBUG_USER = "dev"


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_debug_user: Annotated[str | None, Header()] = None,
) -> User:
    external_id = x_debug_user or DEFAULT_DEBUG_USER

    user = await db.scalar(select(User).where(User.external_id == external_id))
    if user is None:
        user = User(external_id=external_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
