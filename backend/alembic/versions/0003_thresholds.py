"""Stage 2: threshold (versioned, numbered, superseded once, never deleted) and the event trail.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04

Amended on 4 November 2026 after the Feature 2 verification (D30), before it had been
applied to any database: version_no, spine_pm_status_at_set, the CTT consistency check and
the same-engagement successor check were added. From here on this file is a frozen snapshot.
It deliberately repeats the constraint SQL from the models instead of importing it, so a
later change to the models cannot silently rewrite history. tests/test_migration_sql.py
checks that the two agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPINE_PM_STATUSES = "'available', 'not_set', 'not_pinned', 'not_configured', 'unreachable'"

# A threshold row changes once, when it is superseded: superseded_by goes from null to the
# successor's id and nothing else moves (architecture D26). Any other UPDATE is refused for
# every role; DELETE and TRUNCATE go through the append-only function of migration 0001.
SUPERSEDE_ONLY_FUNCTION = """
CREATE FUNCTION oak_misstatements_threshold_supersede_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.superseded_by IS NOT NULL THEN
        RAISE EXCEPTION 'threshold % is superseded and cannot change (architecture D26)', OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF NEW.superseded_by IS NULL
       OR (to_jsonb(NEW) - 'superseded_by') IS DISTINCT FROM (to_jsonb(OLD) - 'superseded_by')
    THEN
        RAISE EXCEPTION 'threshold %: only superseded_by may be set, once (architecture D26)',
            OLD.id USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END
$$
"""

# The successor must be a later version of the same engagement. Checked at COMMIT, as a
# deferred constraint trigger, because the successor row is inserted after the old row has
# been pointed at it (the deferred foreign key allows that order; D26, D30).
SUCCESSOR_FUNCTION = """
CREATE FUNCTION oak_misstatements_threshold_successor_check() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    successor_engagement uuid;
    successor_version integer;
BEGIN
    IF NEW.superseded_by IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT engagement_id, version_no INTO successor_engagement, successor_version
      FROM threshold WHERE id = NEW.superseded_by;
    IF successor_engagement IS NULL THEN
        RAISE EXCEPTION 'threshold %: successor % does not exist', NEW.id, NEW.superseded_by
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF successor_engagement <> NEW.engagement_id THEN
        RAISE EXCEPTION 'threshold %: successor % belongs to another engagement (architecture D30)',
            NEW.id, NEW.superseded_by USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF successor_version <= NEW.version_no THEN
        RAISE EXCEPTION 'threshold %: successor % is not a later version (architecture D30)',
            NEW.id, NEW.superseded_by USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END
$$
"""

GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'oak_misstatements_app') THEN
        GRANT SELECT, INSERT ON threshold, event TO oak_misstatements_app;
        GRANT UPDATE (superseded_by) ON threshold TO oak_misstatements_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "threshold",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("om", sa.Numeric(), nullable=False),
        sa.Column("pm", sa.Numeric(), nullable=False),
        sa.Column("ctt", sa.Numeric(), nullable=False),
        sa.Column("ctt_fraction", sa.Numeric(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("set_by", sa.Text(), nullable=False),
        sa.Column(
            "set_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("superseded_by", sa.Uuid(), nullable=True),
        sa.Column("spine_version_id", sa.Uuid(), nullable=True),
        sa.Column("spine_pm_at_set", sa.Numeric(), nullable=True),
        sa.Column("spine_pm_status_at_set", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_threshold"),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name="fk_threshold_engagement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("engagement_id", "version_no", name="uq_threshold_engagement_version"),
        sa.CheckConstraint("version_no >= 1", name="ck_threshold_version_positive"),
        sa.CheckConstraint("om > 0", name="ck_threshold_om_positive"),
        sa.CheckConstraint("pm > 0", name="ck_threshold_pm_positive"),
        sa.CheckConstraint("ctt > 0", name="ck_threshold_ctt_positive"),
        sa.CheckConstraint(
            "ctt_fraction > 0 AND ctt_fraction < 1", name="ck_threshold_ctt_fraction_range"
        ),
        sa.CheckConstraint("ctt < pm", name="ck_threshold_ctt_below_pm"),
        # The stored amount is PM times the declared fraction, half up to the paisa, exactly
        # as the application computes it (D27, D30). PostgreSQL only: see the model.
        sa.CheckConstraint("ctt = round(pm * ctt_fraction, 2)", name="ck_threshold_ctt_consistent"),
        sa.CheckConstraint("length(trim(basis)) > 0", name="ck_threshold_basis_not_blank"),
        sa.CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id", name="ck_threshold_not_self"
        ),
        sa.CheckConstraint(
            f"spine_pm_status_at_set IN ({SPINE_PM_STATUSES})",
            name="ck_threshold_spine_pm_status",
        ),
        sa.CheckConstraint(
            "(spine_pm_status_at_set = 'available') = (spine_pm_at_set IS NOT NULL)",
            name="ck_threshold_spine_pm_amount_matches_status",
        ),
        sa.CheckConstraint(
            "(spine_pm_status_at_set = 'not_pinned') = (spine_version_id IS NULL)",
            name="ck_threshold_spine_pm_pinned_matches_status",
        ),
    )
    # Deferred to COMMIT: a supersession sets the old row's superseded_by to the new id and
    # only then inserts the new row, so the one-current-per-engagement index below holds at
    # every step (architecture D26).
    op.create_foreign_key(
        "fk_threshold_superseded_by",
        "threshold",
        "threshold",
        ["superseded_by"],
        ["id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "uq_threshold_current",
        "threshold",
        ["engagement_id"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    for column in ("om", "pm", "ctt", "spine_pm_at_set"):
        op.execute(f"ALTER TABLE threshold ALTER COLUMN {column} TYPE money_amount")
    op.execute(SUPERSEDE_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_threshold_supersede_only BEFORE UPDATE ON threshold "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_threshold_supersede_only()"
    )
    op.execute(SUCCESSOR_FUNCTION)
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_threshold_successor_check "
        "AFTER UPDATE OF superseded_by ON threshold DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_threshold_successor_check()"
    )
    op.execute(
        "CREATE TRIGGER trg_threshold_no_delete BEFORE DELETE ON threshold "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_threshold_no_truncate BEFORE TRUNCATE ON threshold "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )

    op.create_table(
        "event",
        # Ordered by an insertion sequence, never by the clock (D30).
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("seq", name="pk_event"),
        sa.UniqueConstraint("id", name="uq_event_id"),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["engagement.id"], name="fk_event_engagement", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(trim(kind)) > 0", name="ck_event_kind_not_blank"),
    )
    op.create_index("ix_event_engagement", "event", ["engagement_id"])
    op.execute(
        "CREATE TRIGGER trg_event_append_only BEFORE UPDATE OR DELETE ON event "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_event_no_truncate BEFORE TRUNCATE ON event "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    )
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_event_no_truncate ON event")
    op.execute("DROP TRIGGER IF EXISTS trg_event_append_only ON event")
    op.drop_index("ix_event_engagement", table_name="event")
    op.drop_table("event")
    op.execute("DROP TRIGGER IF EXISTS trg_threshold_no_truncate ON threshold")
    op.execute("DROP TRIGGER IF EXISTS trg_threshold_no_delete ON threshold")
    op.execute("DROP TRIGGER IF EXISTS trg_threshold_successor_check ON threshold")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_threshold_successor_check()")
    op.execute("DROP TRIGGER IF EXISTS trg_threshold_supersede_only ON threshold")
    op.execute("DROP FUNCTION IF EXISTS oak_misstatements_threshold_supersede_only()")
    op.drop_index("uq_threshold_current", table_name="threshold")
    op.drop_constraint("fk_threshold_superseded_by", "threshold", type_="foreignkey")
    op.drop_table("threshold")
