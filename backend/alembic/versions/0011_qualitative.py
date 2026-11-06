"""The qualitative checklist's record (spec sections 5 and 9; architecture D59).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-06

Spec section 9: ``qualitative  misstatement · factor · note · escalated_by · at``. One row is
one entry against one factor of one misstatement. The table is append-only, like every
other record of the module: recording a factor, recording it again with a new reason and
clearing it are each a new row, told apart by ``applies`` and ordered by ``entry_no``.

The factor is held to the seven of spec section 5 by a CHECK: a new factor needs a new
migration. The reason and the actor are never blank. No existing row or table is touched.
This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FACTORS = (
    "law_or_covenant",
    "earnings_trend",
    "ratio",
    "fraud",
    "related_party",
    "segment_or_remuneration",
    "loss_to_profit",
)

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT ON qualitative TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    listed = ", ".join(f"'{factor}'" for factor in FACTORS)
    op.create_table(
        "qualitative",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("misstatement_id", sa.Uuid(), nullable=False),
        sa.Column("entry_no", sa.Integer(), nullable=False),
        sa.Column("factor", sa.Text(), nullable=False),
        sa.Column("applies", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("escalated_by", sa.Text(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_qualitative"),
        sa.ForeignKeyConstraint(
            ["misstatement_id"],
            ["misstatement.id"],
            name="fk_qualitative_misstatement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("misstatement_id", "entry_no", name="uq_qualitative_entry"),
        sa.CheckConstraint("entry_no >= 1", name="ck_qualitative_entry_positive"),
        sa.CheckConstraint(f"factor IN ({listed})", name="ck_qualitative_factor"),
        sa.CheckConstraint("length(trim(note)) > 0", name="ck_qualitative_note_not_blank"),
        sa.CheckConstraint("length(trim(escalated_by)) > 0", name="ck_qualitative_escalated_by"),
    )
    op.create_index("ix_qualitative_misstatement", "qualitative", ["misstatement_id"])
    op.execute(
        "CREATE TRIGGER trg_qualitative_append_only BEFORE UPDATE OR DELETE ON qualitative "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_qualitative_no_truncate BEFORE TRUNCATE ON qualitative "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_qualitative_no_truncate ON qualitative")
    op.execute("DROP TRIGGER IF EXISTS trg_qualitative_append_only ON qualitative")
    op.drop_index("ix_qualitative_misstatement", table_name="qualitative")
    op.drop_table("qualitative")
