"""Background execution of report runs.

Concurrency is bounded by a module-level semaphore rather than a queue. Reports
beyond the limit simply stay `queued` until a slot frees, which the status model
already expresses — no extra UX. This function is the seam a Postgres-backed
queue replaces later: same statuses, same transitions, different trigger.
"""

import asyncio
import logging

from sqlalchemy import update

from app.config import get_settings
from app.db import SessionLocal
from app.models import Report

log = logging.getLogger(__name__)
_settings = get_settings()

_semaphore = asyncio.Semaphore(_settings.max_concurrent_runs)
_graph = None


def set_graph(graph) -> None:
    global _graph
    _graph = graph


def get_graph():
    if _graph is None:
        raise RuntimeError("graph not initialised; app lifespan did not run")
    return _graph


async def _patch(report_id: int, **fields) -> None:
    """Short-lived session per write.

    Deliberately not one session held across the whole run: a 90s run holding a
    pooled connection, times max_concurrent_runs, exhausts the pool.
    """
    async with SessionLocal() as session:
        await session.execute(update(Report).where(Report.id == report_id).values(**fields))
        await session.commit()


async def run_report(report_id: int, idea: str, target_user: str | None) -> None:
    async with _semaphore:
        try:
            await _patch(report_id, status="running", step="starting")

            graph = get_graph()
            # One checkpoint thread per report — this is what makes a crashed
            # run resumable by id.
            config = {"configurable": {"thread_id": str(report_id)}}
            state = {"report_id": report_id, "idea": idea, "target_user": target_user}

            final: dict = {}
            async for mode, chunk in graph.astream(
                state, config=config, stream_mode=["custom", "values"]
            ):
                if mode == "custom" and isinstance(chunk, dict) and "step" in chunk:
                    await _patch(report_id, step=chunk["step"])
                elif mode == "values":
                    final = chunk

            await _patch(
                report_id,
                status="succeeded",
                step=None,
                report=final.get("report"),
                score=final.get("score"),
            )
        except Exception as exc:  # noqa: BLE001 — must never escape into BackgroundTasks
            log.exception("report %s failed", report_id)
            await _patch(
                report_id,
                status="failed",
                step=None,
                error=f"{type(exc).__name__}: {exc}",
            )
