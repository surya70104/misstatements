"""The per-line classification snapshot of a misstatement version, append-only, no amounts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-04

Architecture D32. One row per adjustment line per misstatement version: the Spine's ledger
identity (key, name, parent chain), the head, nature, Schedule III item and section the
effects were computed on, and the Spine version and tree version they came from. Never a Dr
or a Cr. This file is a frozen snapshot: it repeats the constraint SQL from the model, and
tests/test_migration_sql.py checks that the two agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECTIONS = "'assets', 'liabilities', 'equity', 'pl_before_tax', 'pl_after_tax', 'unresolved'"

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT ON misstatement_line_class TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "misstatement_line_class",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("misstatement_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("ledger_key", sa.Text(), nullable=False),
        sa.Column("ledger_name", sa.Text(), nullable=False),
        sa.Column("parent_chain", postgresql.JSONB(), nullable=False),
        sa.Column("head_id", sa.Text(), nullable=True),
        sa.Column("nature", sa.Text(), nullable=True),
        sa.Column("head_item", sa.Text(), nullable=True),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("spine_version_id", sa.Uuid(), nullable=False),
        sa.Column("tree_version", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_misstatement_line_class"),
        sa.ForeignKeyConstraint(
            ["misstatement_version_id"],
            ["misstatement_version.id"],
            name="fk_line_class_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("misstatement_version_id", "position", name="uq_line_class_position"),
        sa.CheckConstraint("position >= 1", name="ck_line_class_position_positive"),
        sa.CheckConstraint("length(trim(ledger_key)) > 0", name="ck_line_class_key_not_blank"),
        sa.CheckConstraint(f"section IN ({SECTIONS})", name="ck_line_class_section"),
        sa.CheckConstraint("nature IS NULL OR nature IN ('BS', 'PL')", name="ck_line_class_nature"),
    )
    op.create_index("ix_line_class_version", "misstatement_line_class", ["misstatement_version_id"])
    op.execute(
        "CREATE TRIGGER trg_misstatement_line_class_append_only BEFORE UPDATE OR DELETE ON "
        "misstatement_line_class FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_misstatement_line_class_no_truncate BEFORE TRUNCATE ON "
        "misstatement_line_class FOR EACH STATEMENT "
        "EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_misstatement_line_class_no_truncate ON misstatement_line_class"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_misstatement_line_class_append_only ON misstatement_line_class"
    )
    op.drop_index("ix_line_class_version", table_name="misstatement_line_class")
    op.drop_table("misstatement_line_class")
