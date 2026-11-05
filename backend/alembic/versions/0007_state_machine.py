"""The state machine at the database (spec section 3.3; acceptance 3; architecture D41).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-05

Stage 3 moves a misstatement by inserting its next version. This migration makes the rules
of those versions hold for every role, whatever the application does:

- five CHECKs tie the dates and reasons to the state: version 1 is ``raised``; a
  communication date exists exactly when the item has left ``raised``; a decision date
  exists exactly in a final state; a refusal reason, not blank, exists exactly when
  ``refused``; a withdrawal reason, not blank, exactly when ``withdrawn``;
- a trigger on INSERT checks each new version against the latest one: the first is version
  1 and ``raised``; every later one is the next number; and its state is either the same
  open state (a new version without a move) or a move the diagram draws. Nothing follows
  ``corrected``, ``refused`` or ``withdrawn``.

Existing rows are all ``raised`` with no dates and no reasons, so every CHECK holds for
them. This file is a frozen snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_misstatement_version_first_is_raised", "version_no > 1 OR state = 'raised'"),
    (
        "ck_misstatement_version_communicated_at",
        "(state = 'raised') = (communicated_at IS NULL)",
    ),
    (
        "ck_misstatement_version_decided_at",
        "(state IN ('corrected', 'refused', 'withdrawn')) = (decided_at IS NOT NULL)",
    ),
    (
        "ck_misstatement_version_refusal_reason",
        "(state = 'refused') = (refusal_reason IS NOT NULL) "
        "AND (refusal_reason IS NULL OR length(trim(refusal_reason)) > 0)",
    ),
    (
        "ck_misstatement_version_withdrawal_reason",
        "(state = 'withdrawn') = (withdrawal_reason IS NOT NULL) "
        "AND (withdrawal_reason IS NULL OR length(trim(withdrawal_reason)) > 0)",
    ),
)

TRANSITION_FUNCTION = """
CREATE FUNCTION oak_misstatements_version_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    previous record;
BEGIN
    SELECT version_no, state INTO previous
      FROM misstatement_version
     WHERE misstatement_id = NEW.misstatement_id
     ORDER BY version_no DESC
     LIMIT 1;
    IF NOT FOUND THEN
        IF NEW.version_no <> 1 OR NEW.state <> 'raised' THEN
            RAISE EXCEPTION 'misstatement %: the first version is version 1, raised (spec 3.3)',
                NEW.misstatement_id USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.version_no <> previous.version_no + 1 THEN
        RAISE EXCEPTION 'misstatement %: version % does not follow version % (architecture D41)',
            NEW.misstatement_id, NEW.version_no, previous.version_no
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF NEW.state = previous.state AND NEW.state IN ('raised', 'communicated') THEN
        RETURN NEW;
    END IF;
    IF (previous.state = 'raised' AND NEW.state = 'communicated')
       OR (previous.state = 'communicated'
           AND NEW.state IN ('corrected', 'refused', 'withdrawn')) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'misstatement %: % to % is not a move of the state machine (spec section 3.3)',
        NEW.misstatement_id, previous.state, NEW.state
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$
"""


def upgrade() -> None:
    for name, condition in CHECKS:
        op.create_check_constraint(name, "misstatement_version", condition)
    op.execute(TRANSITION_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_misstatement_version_transition BEFORE INSERT ON "
        "misstatement_version FOR EACH ROW "
        "EXECUTE FUNCTION oak_misstatements_version_transition()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_misstatement_version_transition ON misstatement_version")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_version_transition()")
    for name, _condition in reversed(CHECKS):
        op.drop_constraint(name, "misstatement_version", type_="check")
