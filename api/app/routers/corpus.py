"""Read-only proof that the corpus asset is accumulating.

The corpus is write-only in V1 — nothing in the product reads from it — so this
endpoint is the only window into it: row counts, and how much of it is actually
embedded. `embedded < total` is the signal that the embedder is missing or
failing, or that the backfill hasn't run.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Entity, Idea, ResearchChunk

router = APIRouter(prefix="/corpus", tags=["corpus"])


async def _counts(db: AsyncSession, model) -> dict:
    total = await db.scalar(select(func.count()).select_from(model))
    embedded = await db.scalar(
        select(func.count()).select_from(model).where(model.embedding.is_not(None))
    )
    return {"total": total, "embedded": embedded}


@router.get("/stats")
async def corpus_stats(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    return {
        "ideas": await _counts(db, Idea),
        "entities": await _counts(db, Entity),
        "research_chunks": await _counts(db, ResearchChunk),
    }
