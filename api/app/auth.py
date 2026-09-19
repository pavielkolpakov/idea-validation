"""Identity.

Two kinds of caller, one table. An anonymous visitor mints a uuid client-side
and sends it as `X-Anon-Id`; a signed-in user sends a Clerk JWT as
`Authorization: Bearer`, verified against Clerk's JWKS by the injected
`TokenVerifier`. Both resolve to an ordinary `users` row — the anonymous one
carries `external_id = "anon:<uuid>"`.

That sameness is the point: ownership, quota, history and the post-signup claim
all work without a schema change and without an anonymous special case.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User

ANON_PREFIX = "anon:"

_verifier = None


def set_verifier(verifier) -> None:
    global _verifier
    _verifier = verifier


def get_verifier():
    if _verifier is None:
        raise RuntimeError("verifier not initialised; app lifespan did not run")
    return _verifier


async def resolve_external_id(authorization: str | None, x_anon_id: str | None) -> str | None:
    """Map credentials to an `external_id`, or None when there are none valid.

    A present-but-invalid `Authorization` header resolves to None rather than
    falling through to `X-Anon-Id`: a forged token must be rejected, not quietly
    downgraded to an anonymous identity that still gets a free run.
    """
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        return await get_verifier().verify(token.strip())
    if x_anon_id:
        return f"{ANON_PREFIX}{x_anon_id}"
    return None


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_anon_id: Annotated[str | None, Header()] = None,
) -> User:
    external_id = await resolve_external_id(authorization, x_anon_id)
    if external_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.scalar(select(User).where(User.external_id == external_id))
    if user is not None:
        return user

    user = User(external_id=external_id)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Two requests from a brand-new identity race here — a double-clicked
        # submit button is enough. `external_id` is unique, so one insert loses;
        # losing it must return the winner's row, not a 500.
        await db.rollback()
        return await db.scalar(select(User).where(User.external_id == external_id))
    await db.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
