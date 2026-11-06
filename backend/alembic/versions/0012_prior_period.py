"""Prior-period uncorrected misstatements carried forward (SA 450 paragraph 11(b); spec
sections 4.1 and 9; acceptance 5; architecture D61).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-06

Two changes:

- ``prior_period``: one row per version of one carried item of one engagement, append-only
  like every other record of the module. Recording an item, revising its figures and
  removing it from the carry-forward are each a new row.
- ``evaluation.py_carried``: the specification's own column (section 9), added now. It
  holds what a run saw of the carried items, as labels and aggregates. It is nullable: a
  row written before this migration has none. Adding a column changes no existing row.

No existing row is touched. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every figure a carried item states is money: the domain of migration 0001 holds each to
# two decimal places, as it does every other amount of the module.
AMOUNTS = (
    "prior_profit",
    "prior_net_assets",
    "current_profit",
    "current_net_assets",
    "cumulative_profit",
    "cumulative_net_assets",
)

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT ON prior_period TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "prior_period",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.Text(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("carried", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("prior_period", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("source_misstatement_id", sa.Uuid(), nullable=True),
        sa.Column("prior_profit", sa.Numeric(), nullable=True),
        sa.Column("prior_net_assets", sa.Numeric(), nullable=True),
        sa.Column("current_profit", sa.Numeric(), nullable=False),
        sa.Column("current_net_assets", sa.Numeric(), nullable=False),
        sa.Column("cumulative_profit", sa.Numeric(), nullable=False),
        sa.Column("cumulative_net_assets", sa.Numeric(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prior_period"),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name="fk_prior_period_engagement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_misstatement_id"],
            ["misstatement.id"],
            name="fk_prior_period_source_misstatement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("engagement_id", "ref", "version_no", name="uq_prior_period_version"),
        sa.CheckConstraint("version_no >= 1", name="ck_prior_period_version_positive"),
        sa.CheckConstraint("length(trim(ref)) > 0", name="ck_prior_period_ref"),
        sa.CheckConstraint("length(trim(description)) > 0", name="ck_prior_period_description"),
        sa.CheckConstraint("length(trim(prior_period)) > 0", name="ck_prior_period_period"),
        sa.CheckConstraint("length(trim(source_ref)) > 0", name="ck_prior_period_source_ref"),
        sa.CheckConstraint("length(trim(basis)) > 0", name="ck_prior_period_basis_not_blank"),
        sa.CheckConstraint("length(trim(recorded_by)) > 0", name="ck_prior_period_recorded_by"),
        sa.CheckConstraint(
            "(source_misstatement_id IS NULL AND prior_profit IS NULL "
            "AND prior_net_assets IS NULL) OR "
            "(source_misstatement_id IS NOT NULL AND prior_profit IS NOT NULL "
            "AND prior_net_assets IS NOT NULL)",
            name="ck_prior_period_source_complete",
        ),
    )
    op.create_index("ix_prior_period_engagement", "prior_period", ["engagement_id"])
    for column in AMOUNTS:
        op.execute(f"ALTER TABLE prior_period ALTER COLUMN {column} TYPE money_amount")
    op.execute(
        "CREATE TRIGGER trg_prior_period_append_only BEFORE UPDATE OR DELETE ON prior_period "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_prior_period_no_truncate BEFORE TRUNCATE ON prior_period "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)
    op.add_column("evaluation", sa.Column("py_carried", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation", "py_carried")
    op.execute("DROP TRIGGER IF EXISTS trg_prior_period_no_truncate ON prior_period")
    op.execute("DROP TRIGGER IF EXISTS trg_prior_period_append_only ON prior_period")
    op.drop_index("ix_prior_period_engagement", table_name="prior_period")
    op.drop_table("prior_period")
