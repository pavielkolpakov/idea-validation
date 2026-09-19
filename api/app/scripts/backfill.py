"""Backfill the corpus for reports produced before Phase 3 ingest landed.

Phase 2 wrote `research_chunks` with NULL embeddings, no `entities` at all, and
`ideas` with NULL embeddings. This script closes that gap for every `succeeded`
report: embed the idea, upsert entities from the stored competitor table, embed
any chunk still missing a vector.

    cd api && uv run python -m app.scripts.backfill

One caveat: entity upserts are keyed on domain, so re-running against an
already-ingested report inflates `seen_count` for its competitors. Treat this
as a one-shot migration for pre-ingest data, not a cron job.
"""

import asyncio
import logging

from sqlalchemy import select

from app.clients.embeddings import OpenAIEmbedder
from app.config import get_settings
from app.corpus import backfill_report
from app.db import SessionLocal
from app.models import Idea, Report

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def main() -> None:
    if not get_settings().openai_api_key.strip():
        raise SystemExit("OPENAI_API_KEY is required: the backfill embeds everything it writes")
    embedder = OpenAIEmbedder()

    async with SessionLocal() as session:
        reports = (
            await session.scalars(
                select(Report).where(Report.status == "succeeded").order_by(Report.id)
            )
        ).all()

    log.info("backfilling %d succeeded reports", len(reports))
    total_entities = total_chunks = 0

    for report in reports:
        async with SessionLocal() as session:
            entities, chunks = await backfill_report(
                session,
                embedder,
                report=report.report,
                idea=await session.get(Idea, report.idea_id),
                report_id=report.id,
            )
            total_entities += entities
            total_chunks += chunks
            await session.commit()
        log.info("report %s done", report.id)

    log.info(
        "backfill complete: %d entity upserts, %d chunks embedded", total_entities, total_chunks
    )


if __name__ == "__main__":
    asyncio.run(main())
