from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1536  # openai text-embedding-3-small

REPORT_STATUSES = ("queued", "running", "succeeded", "failed")
TERMINAL_STATUSES = ("succeeded", "failed")


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=False), primary_key=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = _pk()
    # Provider-agnostic: Clerk/Auth.js/whatever populates this in Phase 4.
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = _pk()
    text: Mapped[str] = mapped_column(Text)
    target_user: Mapped[str | None] = mapped_column(Text)
    # Populated in Phase 3. No HNSW index until retrieval is switched on.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_reports_status",
        ),
    )

    id: Mapped[int] = _pk()
    public_slug: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id", ondelete="CASCADE"))

    status: Mapped[str] = mapped_column(String(16), default="queued")
    # Free-text progress for the UI. Deliberately not an enum: it changes
    # whenever the graph changes shape, and no code branches on it.
    step: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)

    dossiers_raw: Mapped[dict | None] = mapped_column(JSONB)
    report: Mapped[dict | None] = mapped_column(JSONB)
    score: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Entity(Base):
    """A company/product discovered during research. The corpus asset."""

    __tablename__ = "entities"

    id: Mapped[int] = _pk()
    name: Mapped[str] = mapped_column(String(255))
    # Normalized (scheme/www/path stripped, lowercased) — the dedup key.
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    funding_stage: Mapped[str | None] = mapped_column(String(64))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    # 'web' = found by live research; 'corpus' = surfaced from our own store.
    # Prevents corpus-derived claims being re-ingested as fresh corroboration.
    source: Mapped[str] = mapped_column(String(16), default="web", server_default="web")

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    seen_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ResearchChunk(Base):
    __tablename__ = "research_chunks"

    id: Mapped[int] = _pk()
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    source: Mapped[str] = mapped_column(String(16), default="web", server_default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "period", name="uq_usage_user_period"),)

    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
