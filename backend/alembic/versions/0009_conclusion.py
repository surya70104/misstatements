"""The conclusion on the evaluation row (spec sections 6.4 and 9; acceptance 7, 10; D45).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-05

Spec section 9 puts ``conclusion``, ``basis`` and ``concluded_by`` on the ``evaluation``
row. This migration adds them, with ``determination`` (whether the uncorrected misstatements
are material, the "whether" of section 6.4), as nullable columns: a run recorded without a
conclusion (Stage 4) keeps them null, and a conclusion is a **new** row that carries all
four together with its own figures and threshold version. No existing row is touched; the
append-only triggers of migration 0008 stay as they are.

Rules for every role:

- all four are present, and ``conclusion``, ``basis`` and ``concluded_by`` not blank, or all
  four are absent (acceptance 10: the conclusion cannot be saved empty);
- ``determination`` is ``not_material`` or ``material``;
- who concluded is who made the row;
- the hard gate, as a trigger on INSERT: a row that concludes ``not_material`` is refused
  when either gross aggregate is at or above the overall materiality of its threshold
  version (spec section 7; acceptance 7, "tested as a gate, not a banner"). A gross
  aggregate is never smaller than the net one, so testing the gross tests both.

This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("determination", "conclusion", "basis", "concluded_by")

CHECKS: tuple[tuple[str, str], ...] = (
    (
        "ck_evaluation_conclusion_complete",
        "(determination IS NULL AND conclusion IS NULL AND basis IS NULL "
        "AND concluded_by IS NULL) OR "
        "(determination IS NOT NULL AND conclusion IS NOT NULL AND basis IS NOT NULL "
        "AND concluded_by IS NOT NULL AND length(trim(conclusion)) > 0 "
        "AND length(trim(basis)) > 0 AND length(trim(concluded_by)) > 0)",
    ),
    (
        "ck_evaluation_determination",
        "determination IS NULL OR determination IN ('not_material', 'material')",
    ),
    (
        "ck_evaluation_concluded_by_actor",
        "concluded_by IS NULL OR concluded_by = evaluated_by",
    ),
)

HARD_GATE_FUNCTION = """
CREATE FUNCTION oak_misstatements_evaluation_hard_gate() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    overall numeric;
BEGIN
    IF NEW.determination IS DISTINCT FROM 'not_material' THEN
        RETURN NEW;
    END IF;
    SELECT om INTO overall FROM threshold WHERE id = NEW.threshold_id;
    IF overall IS NOT NULL
       AND (NEW.agg_gross_pbt >= overall OR NEW.agg_gross_na >= overall) THEN
        RAISE EXCEPTION 'evaluation: aggregate at or above OM, not material refused (D45)'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("evaluation", sa.Column(column, sa.Text(), nullable=True))
    for name, condition in CHECKS:
        op.create_check_constraint(name, "evaluation", condition)
    op.execute(HARD_GATE_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_evaluation_hard_gate BEFORE INSERT ON evaluation "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_evaluation_hard_gate()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evaluation_hard_gate ON evaluation")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_evaluation_hard_gate()")
    for name, _condition in reversed(CHECKS):
        op.drop_constraint(name, "evaluation", type_="check")
    for column in reversed(COLUMNS):
        op.drop_column("evaluation", column)
