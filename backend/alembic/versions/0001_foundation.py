"""Foundation: the append-only trigger function and the money domain. No tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-04

Stage 0 creates only what every later table relies on (architecture D6, D16). The threshold,
misstatement, qualitative and evaluation tables of spec section 9 arrive with Stages 1 to 4
in their own migrations. This file is a frozen snapshot; a later change creates a new
migration, never an edit here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spec section 9: misstatement and evaluation are append-only. The function raises for any
# UPDATE, DELETE or TRUNCATE, whoever runs it. The error code is
# integrity_constraint_violation so drivers report it as an integrity error.
APPEND_ONLY_FUNCTION = """
CREATE FUNCTION oak_misstatements_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only: % is not allowed (SA 450; architecture D6)',
        TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END
$$
"""

# Money is never a float (architecture D16): a NUMERIC that refuses more than two decimal
# places (never rounds), NaN, infinity and 10^15 or more. Sign is not restricted here: a
# column that must be positive, such as a Dr or Cr line, adds its own CHECK.
MONEY_DOMAIN = """
CREATE DOMAIN money_amount AS NUMERIC
    CONSTRAINT money_amount_finite CHECK (VALUE <> 'NaN'::numeric AND abs(VALUE) < 1000000000000000)
    CONSTRAINT money_amount_two_places CHECK (scale(VALUE) <= 2)
"""


def upgrade() -> None:
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(MONEY_DOMAIN)


def downgrade() -> None:
    op.execute("DROP DOMAIN IF EXISTS money_amount")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_append_only()")
