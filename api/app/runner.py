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
from app.graph.nodes.prompts import RESEARCH_AGENTS
from app.models import Report, ResearchChunk

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


async def _write_chunks(report_id: int, dossiers: list[dict]) -> None:
    """Persist raw dossiers into the corpus.

    Runs after the report row is written, and swallows its own errors: a corpus
    write must never cost the user their report. Embeddings arrive in Phase 3 —
    the rows are written now because backfilling text is easy and backfilling a
    run that was never recorded is impossible.
    """
    try:
        async with SessionLocal() as session:
            for dossier in dossiers:
                if not (dossier.get("text") or "").strip():
                    continue
                session.add(
                    ResearchChunk(
                        report_id=report_id,
                        agent=dossier["agent"],
                        text=dossier["text"],
                        citations=dossier.get("citations") or [],
                        source="web",
                    )
                )
            await session.commit()
    except Exception:  # noqa: BLE001 — corpus writes are best-effort
        log.exception("corpus write failed for report %s", report_id)


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
            # Research nodes announce completion; the runner aggregates into a
            # count. Four concurrent nodes each writing their own step string
            # would make progress appear to jump around and go backwards.
            done: set[str] = set()

            async for mode, chunk in graph.astream(
                state, config=config, stream_mode=["custom", "values"]
            ):
                if mode == "custom" and isinstance(chunk, dict):
                    if "agent_done" in chunk:
                        done.add(chunk["agent_done"])
                        await _patch(
                            report_id, step=f"researching ({len(done)}/{len(RESEARCH_AGENTS)})"
                        )
                    elif "step" in chunk:
                        await _patch(report_id, step=chunk["step"])
                elif mode == "values":
                    final = chunk

            await _patch(
                report_id,
                status="succeeded",
                step=None,
                report=final.get("report"),
                score=final.get("score"),
                dossiers_raw={"dossiers": final.get("dossiers") or []},
            )
            await _write_chunks(report_id, final.get("dossiers") or [])
        except Exception as exc:  # noqa: BLE001 — must never escape into BackgroundTasks
            log.exception("report %s failed", report_id)
            await _patch(
                report_id,
                status="failed",
                step=None,
                error=f"{type(exc).__name__}: {exc}",
            )
