"""Where a misstatement comes from (spec section 8; architecture D64).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-07

``misstatement_version.origin``: what a source attaches beyond its reference. For an agent
run, the run id and at least one source-row citation; for a review note, the note's
reference and, optionally, a link. A working-paper or manual entry carries none: its
``source_ref`` is the working paper. The column is nullable and no existing row is touched;
the rules below hold every row written from now on, and every existing row satisfies them.
This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORIGIN_PRESENT = "(raised_from IN ('run', 'note')) = (origin IS NOT NULL)"
RUN_ORIGIN = (
    "raised_from <> 'run' OR ("
    "jsonb_typeof(origin) = 'object' "
    "AND jsonb_typeof(origin->'run_id') = 'string' "
    "AND length(trim(origin->>'run_id')) > 0 "
    "AND jsonb_typeof(origin->'citations') = 'array' "
    "AND jsonb_array_length(origin->'citations') >= 1)"
)
NOTE_ORIGIN = (
    "raised_from <> 'note' OR ("
    "jsonb_typeof(origin) = 'object' "
    "AND jsonb_typeof(origin->'note_ref') = 'string' "
    "AND length(trim(origin->>'note_ref')) > 0)"
)


def upgrade() -> None:
    op.add_column("misstatement_version", sa.Column("origin", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_misstatement_version_origin", "misstatement_version", ORIGIN_PRESENT
    )
    op.create_check_constraint(
        "ck_misstatement_version_run_origin", "misstatement_version", RUN_ORIGIN
    )
    op.create_check_constraint(
        "ck_misstatement_version_note_origin", "misstatement_version", NOTE_ORIGIN
    )


def downgrade() -> None:
    op.drop_constraint("ck_misstatement_version_note_origin", "misstatement_version")
    op.drop_constraint("ck_misstatement_version_run_origin", "misstatement_version")
    op.drop_constraint("ck_misstatement_version_origin", "misstatement_version")
    op.drop_column("misstatement_version", "origin")
