"""Background execution of report runs.

Concurrency is bounded by a module-level semaphore rather than a queue. Reports
beyond the limit simply stay `queued` until a slot frees, which the status model
already expresses — no extra UX. This function is the seam a Postgres-backed
queue replaces later: same statuses, same transitions, different trigger.
"""

import asyncio
import logging

from sqlalchemy import update

from app import quota
from app.config import get_settings
from app.corpus import ingest_run
from app.db import SessionLocal
from app.graph.nodes.prompts import RESEARCH_AGENTS
from app.models import Report

log = logging.getLogger(__name__)
_settings = get_settings()

_semaphore = asyncio.Semaphore(_settings.max_concurrent_runs)
_graph = None
_embedder = None


def set_graph(graph) -> None:
    global _graph
    _graph = graph


def get_graph():
    if _graph is None:
        raise RuntimeError("graph not initialised; app lifespan did not run")
    return _graph


def set_embedder(embedder) -> None:
    global _embedder
    _embedder = embedder


async def _patch(report_id: int, **fields) -> None:
    """Short-lived session per write.

    Deliberately not one session held across the whole run: a 90s run holding a
    pooled connection, times max_concurrent_runs, exhausts the pool.
    """
    async with SessionLocal() as session:
        await session.execute(update(Report).where(Report.id == report_id).values(**fields))
        await session.commit()


async def _ingest(
    report_id: int, idea_id: int, idea: str, dossiers: list[dict], report: dict | None
) -> None:
    """Embed and persist the run into the corpus (ideas / entities / chunks).

    Runs after the report row is written, and swallows its own errors: a corpus
    write must never cost the user their report. An embedding failure degrades
    to NULL embeddings — the columns are nullable for exactly this — with the
    rows still written, because backfilling an embedding is easy and
    backfilling a run that was never recorded is impossible.
    """
    try:
        async with SessionLocal() as session:
            await ingest_run(
                session,
                _embedder,
                report_id=report_id,
                idea_id=idea_id,
                idea_text=idea,
                dossiers=dossiers,
                report=report,
            )
    except Exception:  # noqa: BLE001 — corpus writes are best-effort
        log.exception("corpus ingest failed for report %s", report_id)


async def run_report(report_id: int, idea_id: int, idea: str, target_user: str | None) -> None:
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
            await _ingest(
                report_id, idea_id, idea, final.get("dossiers") or [], final.get("report")
            )
        except Exception as exc:  # noqa: BLE001 — must never escape into BackgroundTasks
            log.exception("report %s failed", report_id)
            # The user should not pay for our failure. Best-effort, like the
            # corpus write: a refund that raises must not replace the real error.
            try:
                await quota.refund_for_report(report_id)
            except Exception:  # noqa: BLE001
                log.exception("quota refund failed for report %s", report_id)
            await _patch(
                report_id,
                status="failed",
                step=None,
                error=f"{type(exc).__name__}: {exc}",
            )
