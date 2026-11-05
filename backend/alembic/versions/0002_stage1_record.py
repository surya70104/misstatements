"""Stage 1: engagement, misstatement and misstatement_version; the last two append-only.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04

This file is a frozen snapshot. It deliberately repeats the constraint SQL from the models
instead of importing it, so a later change to the models cannot silently rewrite history.
tests/test_migration_sql.py checks that the two agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES = "'factual', 'judgemental', 'projected'"
SOURCES = "'wp', 'run', 'note', 'manual'"
STATES = "'raised', 'communicated', 'corrected', 'refused', 'withdrawn'"
KINDS = "'reclass', 'correction'"

# Table rights for the application role (architecture D5, D6). The role is cluster-wide and
# created by scripts/db/02_create.sql; the IF EXISTS keeps the migration valid on a cluster
# without it. misstatement and misstatement_version get SELECT and INSERT only: the second
# layer of append-only.
GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT, UPDATE ON engagement TO oak_misstatements_app;
        GRANT SELECT, INSERT ON misstatement, misstatement_version TO oak_misstatements_app;
    END IF;
END
$$
"""


def _append_only(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )


def upgrade() -> None:
    op.create_table(
        "engagement",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("spine_engagement_id", sa.Uuid(), nullable=True),
        sa.Column("spine_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_engagement"),
        sa.CheckConstraint("length(trim(label)) > 0", name="ck_engagement_label_not_blank"),
        sa.CheckConstraint(
            "spine_version_id IS NULL OR spine_engagement_id IS NOT NULL",
            name="ck_engagement_version_needs_engagement",
        ),
    )
    op.create_table(
        "misstatement",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("ref_no", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_misstatement"),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name="fk_misstatement_engagement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("engagement_id", "ref_no", name="uq_misstatement_engagement_ref"),
        sa.CheckConstraint("ref_no >= 1", name="ck_misstatement_ref_positive"),
    )
    op.create_table(
        "misstatement_version",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("misstatement_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("raised_by", sa.Text(), nullable=False),
        sa.Column("raised_from", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="raised", nullable=False),
        sa.Column("communicated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refusal_reason", sa.Text(), nullable=True),
        sa.Column("withdrawal_reason", sa.Text(), nullable=True),
        sa.Column("spine_adjustment_id", sa.Uuid(), nullable=False),
        sa.Column("spine_kind", sa.Text(), nullable=False),
        sa.Column("range_low", sa.Numeric(), nullable=True),
        sa.Column("range_high", sa.Numeric(), nullable=True),
        sa.Column("sample_ref", sa.Text(), nullable=True),
        sa.Column("projection_basis", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_misstatement_version"),
        sa.ForeignKeyConstraint(
            ["misstatement_id"],
            ["misstatement.id"],
            name="fk_misstatement_version_misstatement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("misstatement_id", "version_no", name="uq_misstatement_version_no"),
        sa.CheckConstraint("version_no >= 1", name="ck_misstatement_version_positive"),
        sa.CheckConstraint(f"type IN ({TYPES})", name="ck_misstatement_version_type"),
        sa.CheckConstraint(f"raised_from IN ({SOURCES})", name="ck_misstatement_version_source"),
        sa.CheckConstraint(f"state IN ({STATES})", name="ck_misstatement_version_state"),
        sa.CheckConstraint(f"spine_kind IN ({KINDS})", name="ck_misstatement_version_kind"),
        sa.CheckConstraint(
            "length(trim(description)) > 0", name="ck_misstatement_version_description"
        ),
        sa.CheckConstraint(
            "length(trim(source_ref)) > 0", name="ck_misstatement_version_source_ref"
        ),
        sa.CheckConstraint(
            "(type <> 'judgemental') OR "
            "(range_low IS NOT NULL AND range_high IS NOT NULL AND range_low <= range_high)",
            name="ck_misstatement_version_judgemental_range",
        ),
        sa.CheckConstraint(
            "(type = 'judgemental') OR (range_low IS NULL AND range_high IS NULL)",
            name="ck_misstatement_version_range_only_judgemental",
        ),
        sa.CheckConstraint(
            "(type <> 'projected') OR (sample_ref IS NOT NULL AND projection_basis IS NOT NULL)",
            name="ck_misstatement_version_projected_fields",
        ),
        sa.CheckConstraint(
            "(type = 'projected') OR (sample_ref IS NULL AND projection_basis IS NULL)",
            name="ck_misstatement_version_projection_only_projected",
        ),
    )
    op.create_index(
        "ix_misstatement_version_misstatement", "misstatement_version", ["misstatement_id"]
    )
    # Money is the domain migration 0001 created (D16).
    op.execute("ALTER TABLE misstatement_version ALTER COLUMN range_low TYPE money_amount")
    op.execute("ALTER TABLE misstatement_version ALTER COLUMN range_high TYPE money_amount")
    _append_only("misstatement")
    _append_only("misstatement_version")
    op.execute(GRANTS)


def downgrade() -> None:
    for table in ("misstatement_version", "misstatement"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.drop_index("ix_misstatement_version_misstatement", table_name="misstatement_version")
    op.drop_table("misstatement_version")
    op.drop_table("misstatement")
    op.drop_table("engagement")
