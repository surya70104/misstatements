"""Performance materiality must be below overall materiality (B13, architecture D34).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04

One CHECK on ``threshold``: ``pm < om``. SA 320 paragraph 9 defines performance materiality
as an amount set at less than materiality for the financial statements as a whole, so an
equal value is refused too. Adding the constraint validates every existing row; a row with
PM at or above OM would stop the migration, which is the right outcome, since no such row
can have been written through the API. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint("ck_threshold_pm_below_om", "threshold", "pm < om")


def downgrade() -> None:
    op.drop_constraint("ck_threshold_pm_below_om", "threshold", type_="check")
