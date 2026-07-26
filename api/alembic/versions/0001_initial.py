"""initial schema: corpus + reports

Revision ID: 0001
Revises:
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Owned by LangGraph's checkpointer, not by Alembic. See alembic/env.py.
    op.execute('CREATE SCHEMA IF NOT EXISTS "langgraph"')

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("external_id", sa.String(255), unique=True),
        sa.Column("email", sa.String(320)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "ideas",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text()),
        # Populated in Phase 3. No HNSW index until retrieval is switched on —
        # the index taxes every insert and nothing reads it in V1.
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("public_slug", sa.String(24), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "idea_id",
            sa.BigInteger(),
            sa.ForeignKey("ideas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("step", sa.String(120)),
        sa.Column("error", sa.Text()),
        sa.Column("dossiers_raw", postgresql.JSONB()),
        sa.Column("report", postgresql.JSONB()),
        sa.Column("score", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_reports_status",
        ),
    )
    op.create_index("ix_reports_public_slug", "reports", ["public_slug"], unique=True)

    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        # Normalized (scheme/www/path stripped, lowercased) — the dedup key.
        sa.Column("domain", sa.String(255), unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("funding_stage", sa.String(64)),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM)),
        # 'web' vs 'corpus': stops corpus-derived claims being re-ingested as
        # fresh corroboration once retrieval is switched on.
        sa.Column("source", sa.String(16), nullable=False, server_default="web"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "research_chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "report_id",
            sa.BigInteger(),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB()),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM)),
        sa.Column("source", sa.String(16), nullable=False, server_default="web"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "period", name="uq_usage_user_period"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("research_chunks")
    op.drop_table("entities")
    op.drop_index("ix_reports_public_slug", table_name="reports")
    op.drop_table("reports")
    op.drop_table("ideas")
    op.drop_table("users")
    # Extension and langgraph schema are intentionally left in place.
