"""The evaluation row: append-only, one row per evaluation run (spec section 9; D43).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05

``evaluation`` records each evaluation run: the engagement, the threshold version it was
run against, the four aggregates of spec section 4.1, that materiality was reassessed first
(SA 450 paragraph 10), who ran it and when, and a ``detail`` document of labels and
aggregates. It holds no Dr, no Cr and no single misstatement's effect.

Rules for every role: the four aggregate columns take the money domain of migration 0001;
a gross aggregate is never negative and a net aggregate never exceeds it in size; the row is
append-only through the function of migration 0001 (UPDATE, DELETE and TRUNCATE refused);
and a trigger on INSERT requires the threshold version to belong to the same engagement and
to be the current one, so a run is never recorded against a superseded version. The
application role gets SELECT and INSERT only.

The ``conclusion``, ``basis`` and ``concluded_by`` columns of the spec's row arrive with the
conclusion (Stage 5); ``py_carried`` with the prior-period carry-forward (Pass 2). This file
is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGGREGATES = ("agg_gross_pbt", "agg_net_pbt", "agg_gross_na", "agg_net_na")

THRESHOLD_FUNCTION = """
CREATE FUNCTION oak_misstatements_evaluation_threshold() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    version record;
BEGIN
    SELECT engagement_id, superseded_by INTO version
      FROM threshold
     WHERE id = NEW.threshold_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'evaluation: threshold version % does not exist', NEW.threshold_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF version.engagement_id <> NEW.engagement_id THEN
        RAISE EXCEPTION 'evaluation: threshold version % belongs to another engagement',
            NEW.threshold_id USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF version.superseded_by IS NOT NULL THEN
        RAISE EXCEPTION 'evaluation: threshold version % is superseded (architecture D43)',
            NEW.threshold_id USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$
"""

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT ON evaluation TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "evaluation",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("run_no", sa.Integer(), nullable=False),
        sa.Column("threshold_id", sa.Uuid(), nullable=False),
        sa.Column("agg_gross_pbt", sa.Numeric(), nullable=False),
        sa.Column("agg_net_pbt", sa.Numeric(), nullable=False),
        sa.Column("agg_gross_na", sa.Numeric(), nullable=False),
        sa.Column("agg_net_na", sa.Numeric(), nullable=False),
        sa.Column("materiality_reassessed", sa.Boolean(), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("evaluated_by", sa.Text(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation"),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name="fk_evaluation_engagement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["threshold_id"], ["threshold.id"], name="fk_evaluation_threshold", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("engagement_id", "run_no", name="uq_evaluation_engagement_run"),
        sa.CheckConstraint("run_no >= 1", name="ck_evaluation_run_positive"),
        sa.CheckConstraint(
            "agg_gross_pbt >= 0 AND agg_gross_na >= 0", name="ck_evaluation_gross_not_negative"
        ),
        sa.CheckConstraint(
            "abs(agg_net_pbt) <= agg_gross_pbt AND abs(agg_net_na) <= agg_gross_na",
            name="ck_evaluation_net_within_gross",
        ),
        sa.CheckConstraint("materiality_reassessed", name="ck_evaluation_materiality_reassessed"),
        sa.CheckConstraint("length(trim(evaluated_by)) > 0", name="ck_evaluation_evaluated_by"),
    )
    op.create_index("ix_evaluation_engagement", "evaluation", ["engagement_id"])
    for column in AGGREGATES:
        op.execute(f"ALTER TABLE evaluation ALTER COLUMN {column} TYPE money_amount")
    op.execute(THRESHOLD_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_evaluation_threshold BEFORE INSERT ON evaluation "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_evaluation_threshold()"
    )
    op.execute(
        "CREATE TRIGGER trg_evaluation_append_only BEFORE UPDATE OR DELETE ON evaluation "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_evaluation_no_truncate BEFORE TRUNCATE ON evaluation "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evaluation_no_truncate ON evaluation")
    op.execute("DROP TRIGGER IF EXISTS trg_evaluation_append_only ON evaluation")
    op.execute("DROP TRIGGER IF EXISTS trg_evaluation_threshold ON evaluation")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_evaluation_threshold()")
    op.drop_index("ix_evaluation_engagement", table_name="evaluation")
    op.drop_table("evaluation")
