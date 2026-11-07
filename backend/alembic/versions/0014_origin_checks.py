"""The origin checks of 0013, completed so that a missing key fails (architecture D64).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-07

In PostgreSQL a CHECK whose result is NULL passes, and ``jsonb_typeof(origin->'run_id')``
is NULL when the key is missing. So the two shape checks of 0013 let a run with no
``run_id``, or a note with no ``note_ref``, through. This migration adds two further checks
that read a missing key as the empty string, which fails. Nothing is dropped: 0013's checks
stay, as every migration after 0007 adds rules and removes none. No row is touched, and no
existing row is refused by the tighter rule. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_ORIGIN_NAMED = (
    "raised_from <> 'run' OR ("
    "COALESCE(jsonb_typeof(origin), '') = 'object' "
    "AND COALESCE(jsonb_typeof(origin->'run_id'), '') = 'string' "
    "AND length(trim(COALESCE(origin->>'run_id', ''))) > 0 "
    "AND COALESCE(jsonb_typeof(origin->'citations'), '') = 'array' "
    "AND jsonb_array_length(origin->'citations') >= 1)"
)
NOTE_ORIGIN_NAMED = (
    "raised_from <> 'note' OR ("
    "COALESCE(jsonb_typeof(origin), '') = 'object' "
    "AND COALESCE(jsonb_typeof(origin->'note_ref'), '') = 'string' "
    "AND length(trim(COALESCE(origin->>'note_ref', ''))) > 0)"
)


def upgrade() -> None:
    op.create_check_constraint(
        "ck_misstatement_version_run_origin_named", "misstatement_version", RUN_ORIGIN_NAMED
    )
    op.create_check_constraint(
        "ck_misstatement_version_note_origin_named", "misstatement_version", NOTE_ORIGIN_NAMED
    )


def downgrade() -> None:
    op.drop_constraint("ck_misstatement_version_note_origin_named", "misstatement_version")
    op.drop_constraint("ck_misstatement_version_run_origin_named", "misstatement_version")
