"""The registered working paper (SA 230; spec section 6 item 5; architecture D66).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-07

``working_paper``: one row per export of one engagement, append-only like every other
record of the module. It holds the generated paper's whole content, the SHA-256 of its
canonical JSON, and the evaluation run it rests on. Nothing is dropped and no existing row
is touched. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT ON working_paper TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "working_paper",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("paper_no", sa.Integer(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("generated_by", sa.Text(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_working_paper"),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name="fk_working_paper_engagement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation.id"],
            name="fk_working_paper_evaluation_run",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("engagement_id", "paper_no", name="uq_working_paper_no"),
        sa.CheckConstraint("paper_no >= 1", name="ck_working_paper_no_positive"),
        sa.CheckConstraint(
            "length(content_hash) = 64 AND content_hash = lower(content_hash)",
            name="ck_working_paper_hash",
        ),
        sa.CheckConstraint("length(trim(generated_by)) > 0", name="ck_working_paper_generated_by"),
    )
    op.create_index("ix_working_paper_engagement", "working_paper", ["engagement_id"])
    op.execute(
        "CREATE TRIGGER trg_working_paper_append_only BEFORE UPDATE OR DELETE ON working_paper "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_working_paper_no_truncate BEFORE TRUNCATE ON working_paper "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_working_paper_no_truncate ON working_paper")
    op.execute("DROP TRIGGER IF EXISTS trg_working_paper_append_only ON working_paper")
    op.drop_index("ix_working_paper_engagement", table_name="working_paper")
    op.drop_table("working_paper")
