"""Spend control.

The check and the increment are **one statement**. A `SELECT` then `UPDATE`
races a double-clicked submit button, and losing that race costs a real Opus
call plus four Sonar calls — so "over quota" is expressed as the absence of a
returned row, which Postgres decides atomically.

Anonymous visitors are counted under the sentinel period `'anon'` rather than
the current month. Their id lives in `localStorage` and survives a month
rollover, so a monthly period would hand out a fresh free run every January.
`usage_counters.period` is `String(7)`, which the sentinel fits exactly.
"""

import hashlib
import time
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import ANON_PREFIX
from app.config import get_settings
from app.models import Report, UsageCounter, User

ANON_PERIOD = "anon"

_settings = get_settings()


def is_anonymous(user: User) -> bool:
    return bool(user.external_id and user.external_id.startswith(ANON_PREFIX))


def period_for(user: User) -> str:
    return ANON_PERIOD if is_anonymous(user) else datetime.now(UTC).strftime("%Y-%m")


def limit_for(user: User) -> int:
    return _settings.anon_free_runs if is_anonymous(user) else _settings.monthly_free_runs


def reason_for(user: User) -> str:
    return "anon_quota" if is_anonymous(user) else "user_quota"


async def consume(db: AsyncSession, user: User) -> bool:
    """Claim one run. Returns False when the caller is already at the limit."""
    stmt = (
        insert(UsageCounter)
        .values(user_id=user.id, period=period_for(user), count=1)
        .on_conflict_do_update(
            index_elements=["user_id", "period"],
            set_={"count": UsageCounter.__table__.c.count + 1},
            where=UsageCounter.__table__.c.count < limit_for(user),
        )
        .returning(UsageCounter.count)
    )
    granted = await db.scalar(stmt)
    await db.commit()
    return granted is not None


async def refund_for_report(report_id: int) -> None:
    """Give back the credit a failed run consumed.

    Opens its own session, matching the runner's short-lived-session convention:
    this is called from the failure path, where no request session exists.
    """
    from app.db import SessionLocal

    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).join(Report, Report.user_id == User.id).where(Report.id == report_id)
        )
        if user is None:
            return
        await session.execute(
            update(UsageCounter)
            .where(
                UsageCounter.user_id == user.id,
                UsageCounter.period == period_for(user),
                UsageCounter.count > 0,
            )
            .values(count=UsageCounter.count - 1)
        )
        await session.commit()


# Hashed ip -> (count, window start). In memory on purpose: this is a speed bump
# in front of a wall (the second run needs an account), and a single replica
# makes a shared store unnecessary. It resets on deploy, which costs a few extra
# free runs and no correctness.
_ip_hits: dict[str, tuple[int, float]] = {}


def client_ip(request) -> str:
    """The caller's address, hashed.

    Read straight off `request.client` rather than parsing `X-Forwarded-For`
    here: uvicorn's `--proxy-headers` already rewrites it using the trusted-proxy
    list, and hand-parsing the header means taking a client-controlled value —
    an attacker sending a fresh spoofed first hop per request would defeat the
    cap entirely. Behind a proxy without `--proxy-headers`, every visitor shares
    one bucket, so that flag is load-bearing in production.
    """
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode()).hexdigest()


async def ip_allowed(request) -> bool:
    """Claim one anonymous run against the caller's address."""
    key = client_ip(request)
    now = time.monotonic()
    count, started = _ip_hits.get(key, (0, now))
    if now - started >= _settings.anon_ip_window_s:
        count, started = 0, now
    if count >= _settings.anon_runs_per_ip:
        return False
    _ip_hits[key] = (count + 1, started)
    return True
