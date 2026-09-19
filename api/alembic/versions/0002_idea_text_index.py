"""idea text hash index, for per-user duplicate detection

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Functional, not a column: the duplicate check compares md5(ideas.text), so
    # the index has to be on the same expression the query uses or Postgres
    # falls back to an unindexed scan over a Text column.
    op.execute("CREATE INDEX ix_ideas_text_md5 ON ideas (md5(text))")


def downgrade() -> None:
    op.execute("DROP INDEX ix_ideas_text_md5")
