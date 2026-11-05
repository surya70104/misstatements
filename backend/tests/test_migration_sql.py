"""Migrations 0001 and 0002 rendered offline: no database, no connection.

The URL points at the loopback host as the guard requires, but Alembic runs in SQL mode, so
nothing is connected to. A URL for another module's database or role is refused by env.py
before any of that. The models and the frozen migration must agree.
"""

from __future__ import annotations

import io
import re
from functools import cache

import pytest
from alembic import command

from oak_misstatements.db import Base
from tests.conftest import alembic_config

HERE = "postgresql+psycopg://oak_misstatements_owner:x@localhost:5432/oak_misstatements_test"
ELSEWHERE = "postgresql+psycopg://oak_misstatements_owner:x@localhost:5432/oak_spine"
WRONG_ROLE = "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/oak_misstatements_test"
OFF_HOST = "postgresql+psycopg://oak_misstatements_owner:x@db.example:5432/oak_misstatements_test"
APPEND_ONLY = ("misstatement", "misstatement_version")


@cache
def rendered(direction: str) -> str:
    buffer = io.StringIO()
    cfg = alembic_config(HERE, output=buffer)
    if direction == "upgrade":
        command.upgrade(cfg, "head", sql=True)
    else:
        command.downgrade(cfg, "head:base", sql=True)
    return buffer.getvalue()


def table_block(sql: str, table: str) -> str:
    start = sql.index(f"CREATE TABLE {table} (")
    return sql[start : sql.index(";", start)]


def test_upgrade_creates_the_append_only_function() -> None:
    sql = rendered("upgrade")
    assert "CREATE FUNCTION oak_misstatements_append_only() RETURNS trigger" in sql
    assert "USING ERRCODE = 'integrity_constraint_violation'" in sql


def test_upgrade_creates_the_money_domain() -> None:
    sql = rendered("upgrade")
    assert "CREATE DOMAIN money_amount AS NUMERIC" in sql
    assert "scale(VALUE) <= 2" in sql
    assert "VALUE <> 'NaN'::numeric" in sql
    assert "abs(VALUE) < 1000000000000000" in sql


def test_upgrade_creates_exactly_the_stage_1_and_2_tables() -> None:
    created = re.findall(r"CREATE TABLE (\w+)", rendered("upgrade"))
    assert created == [
        "alembic_version",
        "engagement",
        "misstatement",
        "misstatement_version",
        "threshold",
        "event",
        "misstatement_line_class",
        "evaluation",
    ]


def test_the_classification_snapshot_is_append_only_and_carries_no_amount() -> None:
    sql = rendered("upgrade")
    block = table_block(sql, "misstatement_line_class")
    assert "NUMERIC" not in block and "money_amount" not in block
    assert "parent_chain JSONB NOT NULL" in block
    assert "CONSTRAINT uq_line_class_position UNIQUE (misstatement_version_id, position)" in block
    assert (
        "CREATE TRIGGER trg_misstatement_line_class_append_only BEFORE UPDATE OR DELETE ON "
        "misstatement_line_class FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    ) in sql
    assert "CREATE TRIGGER trg_misstatement_line_class_no_truncate BEFORE TRUNCATE" in sql
    assert "GRANT SELECT, INSERT ON misstatement_line_class TO oak_misstatements_app" in sql
    for line in sql.splitlines():
        if "GRANT" in line and "misstatement_line_class" in line:
            assert "UPDATE" not in line and "DELETE" not in line


def test_threshold_is_superseded_once_and_never_deleted_at_the_database() -> None:
    sql = rendered("upgrade")
    assert "CREATE FUNCTION oak_misstatements_threshold_supersede_only() RETURNS trigger" in sql
    assert "OLD.superseded_by IS NOT NULL" in sql
    assert (
        "(to_jsonb(NEW) - 'superseded_by') IS DISTINCT FROM (to_jsonb(OLD) - 'superseded_by')"
        in sql
    )
    assert (
        "CREATE TRIGGER trg_threshold_supersede_only BEFORE UPDATE ON threshold "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_threshold_supersede_only()"
    ) in sql
    assert (
        "CREATE TRIGGER trg_threshold_no_delete BEFORE DELETE ON threshold "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    ) in sql
    assert "CREATE TRIGGER trg_threshold_no_truncate BEFORE TRUNCATE ON threshold" in sql
    assert "GRANT SELECT, INSERT ON threshold, event TO oak_misstatements_app" in sql
    assert "GRANT UPDATE (superseded_by) ON threshold TO oak_misstatements_app" in sql
    assert (
        "CREATE UNIQUE INDEX uq_threshold_current ON threshold (engagement_id) "
        "WHERE superseded_by IS NULL"
    ) in sql
    for column in ("om", "pm", "ctt", "spine_pm_at_set"):
        assert f"ALTER TABLE threshold ALTER COLUMN {column} TYPE money_amount" in sql
    # D-10: the successor is checked at COMMIT by a deferred constraint trigger.
    assert "CREATE FUNCTION oak_misstatements_threshold_successor_check() RETURNS trigger" in sql
    assert "belongs to another engagement" in sql
    assert "is not a later version" in sql
    assert (
        "CREATE CONSTRAINT TRIGGER trg_threshold_successor_check "
        "AFTER UPDATE OF superseded_by ON threshold DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_threshold_successor_check()"
    ) in sql
    block = table_block(sql, "threshold")
    # D-5: the stored amount is tied to PM and the declared fraction, half up to the paisa.
    assert (
        "CONSTRAINT ck_threshold_ctt_consistent CHECK (ctt = round(pm * ctt_fraction, 2))" in block
    )
    assert "DEFERRABLE INITIALLY DEFERRED" in sql  # fk_threshold_superseded_by
    for name in (
        "uq_threshold_engagement_version",
        "ck_threshold_version_positive",
        "ck_threshold_spine_pm_status",
        "ck_threshold_spine_pm_amount_matches_status",
        "ck_threshold_spine_pm_pinned_matches_status",
        "ck_threshold_ctt_fraction_range",
        "ck_threshold_ctt_below_pm",
        "ck_threshold_basis_not_blank",
        "ck_threshold_not_self",
    ):
        assert name in block


def test_event_is_append_only_at_the_database() -> None:
    sql = rendered("upgrade")
    assert (
        "CREATE TRIGGER trg_event_append_only BEFORE UPDATE OR DELETE ON event "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    ) in sql
    assert "CREATE TRIGGER trg_event_no_truncate BEFORE TRUNCATE ON event" in sql
    block = table_block(sql, "event")
    assert "payload JSONB NOT NULL" in block
    # D-8 for the trail: ordered by an insertion sequence, never by the clock (D30).
    assert "seq BIGINT GENERATED ALWAYS AS IDENTITY" in block
    assert "CONSTRAINT pk_event PRIMARY KEY (seq)" in block
    assert "CONSTRAINT uq_event_id UNIQUE (id)" in block


def test_upgrade_creates_every_model_table_with_every_column() -> None:
    sql = rendered("upgrade")
    for table in Base.metadata.tables.values():
        block = table_block(sql, table.name)
        for column in table.columns:
            # In the CREATE TABLE of its first migration, or added by a later one (0009).
            created = re.search(rf'^\s+"?{re.escape(column.name)}"? [A-Z]', block, re.M)
            added = f"ALTER TABLE {table.name} ADD COLUMN {column.name} " in sql
            assert created or added, f"{table.name}.{column.name} not in migration"


def test_upgrade_declares_every_named_model_constraint() -> None:
    sql = rendered("upgrade")
    # A constraint is either in the CREATE TABLE block (its first migration) or added later by
    # ALTER TABLE ... ADD CONSTRAINT (a following migration, such as 0005). Both count.
    for table in Base.metadata.tables.values():
        block = table_block(sql, table.name)
        for constraint in table.constraints:
            if isinstance(constraint.name, str):
                added = f"ALTER TABLE {table.name} ADD CONSTRAINT {constraint.name} " in sql
                assert constraint.name in block or added, (
                    f"{constraint.name} missing from every migration"
                )


def test_pm_below_om_is_a_database_check_added_by_0005() -> None:
    sql = rendered("upgrade")
    assert "ALTER TABLE threshold ADD CONSTRAINT ck_threshold_pm_below_om CHECK (pm < om)" in sql
    assert "ck_threshold_pm_below_om" not in table_block(sql, "threshold")  # 0003 stays frozen
    down = rendered("downgrade")
    assert "ALTER TABLE threshold DROP CONSTRAINT ck_threshold_pm_below_om" in down
    assert down.index("DROP CONSTRAINT ck_threshold_pm_below_om") < down.index(
        "DROP TABLE threshold;"
    )


def test_the_record_tables_are_append_only_at_the_database() -> None:
    sql = rendered("upgrade")
    for table in APPEND_ONLY:
        assert (
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
        ) in sql
        assert (
            f"CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
        ) in sql


def test_the_application_role_gets_insert_but_never_update_or_delete_on_them() -> None:
    sql = rendered("upgrade")
    assert "GRANT SELECT, INSERT, UPDATE ON engagement TO oak_misstatements_app" in sql
    assert (
        "GRANT SELECT, INSERT ON misstatement, misstatement_version TO oak_misstatements_app" in sql
    )
    for line in sql.splitlines():
        if "GRANT" in line and " ON misstatement" in line:
            assert "UPDATE" not in line and "DELETE" not in line


def test_money_columns_take_the_domain() -> None:
    sql = rendered("upgrade")
    for column in ("range_low", "range_high"):
        assert f"ALTER TABLE misstatement_version ALTER COLUMN {column} TYPE money_amount" in sql


def test_downgrade_removes_everything_it_created() -> None:
    sql = rendered("downgrade")
    for table in (
        "misstatement_line_class",
        "event",
        "threshold",
        "misstatement_version",
        "misstatement",
        "engagement",
    ):
        assert f"DROP TABLE {table};" in sql
    assert sql.index("DROP TABLE misstatement_line_class;") < sql.index("DROP TABLE event;")
    assert sql.index("DROP TABLE event;") < sql.index("DROP TABLE threshold;")
    assert sql.index("DROP TABLE threshold;") < sql.index("DROP TABLE misstatement_version;")
    assert sql.index("DROP TABLE misstatement_version;") < sql.index("DROP TABLE misstatement;")
    assert sql.index("DROP TABLE misstatement;") < sql.index("DROP TABLE engagement;")
    assert "DROP FUNCTION IF EXISTS oak_misstatements_threshold_supersede_only()" in sql
    assert "DROP FUNCTION IF EXISTS oak_misstatements_threshold_successor_check()" in sql
    assert "DROP TRIGGER IF EXISTS trg_threshold_successor_check ON threshold" in sql
    assert "DROP DOMAIN IF EXISTS money_amount" in sql
    assert "DROP FUNCTION IF EXISTS oak_misstatements_append_only()" in sql


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (ELSEWHERE, "never connects to any other database"),
        (WRONG_ROLE, "must connect as oak_misstatements_owner"),
        (OFF_HOST, "loopback interface"),
    ],
)
def test_migration_refuses_other_databases_roles_and_hosts(url: str, message: str) -> None:
    cfg = alembic_config(url, output=io.StringIO())
    with pytest.raises(ValueError, match=message):
        command.upgrade(cfg, "head", sql=True)


def test_the_engagement_audit_columns_are_frozen_by_0006() -> None:
    sql = rendered("upgrade")
    assert "CREATE FUNCTION oak_misstatements_engagement_link_only() RETURNS trigger" in sql
    assert "(to_jsonb(NEW) - 'spine_engagement_id' - 'spine_version_id')" in sql
    assert (
        "CREATE TRIGGER trg_engagement_link_only BEFORE UPDATE ON engagement "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_engagement_link_only()"
    ) in sql
    assert "CREATE TRIGGER trg_engagement_no_delete BEFORE DELETE ON engagement" in sql
    assert "CREATE TRIGGER trg_engagement_no_truncate BEFORE TRUNCATE ON engagement" in sql
    # 0002 granted the whole row; 0006 narrows it to the two link columns.
    assert "GRANT SELECT, INSERT, UPDATE ON engagement TO oak_misstatements_app" in sql
    assert "REVOKE UPDATE ON engagement FROM oak_misstatements_app" in sql
    assert (
        "GRANT UPDATE (spine_engagement_id, spine_version_id) ON engagement "
        "TO oak_misstatements_app"
    ) in sql
    assert sql.index("REVOKE UPDATE ON engagement") > sql.index(
        "GRANT SELECT, INSERT, UPDATE ON engagement"
    )
    down = rendered("downgrade")
    assert "DROP FUNCTION IF EXISTS oak_misstatements_engagement_link_only()" in down
    assert "GRANT UPDATE ON engagement TO oak_misstatements_app" in down


def test_the_state_machine_is_held_at_the_database_by_0007() -> None:
    sql = rendered("upgrade")
    for name, condition in (
        ("ck_misstatement_version_first_is_raised", "version_no > 1 OR state = 'raised'"),
        (
            "ck_misstatement_version_communicated_at",
            "(state = 'raised') = (communicated_at IS NULL)",
        ),
        (
            "ck_misstatement_version_decided_at",
            "(state IN ('corrected', 'refused', 'withdrawn')) = (decided_at IS NOT NULL)",
        ),
    ):
        assert (
            f"ALTER TABLE misstatement_version ADD CONSTRAINT {name} CHECK ({condition})" in sql
        ), name
    # Acceptance 3 at the database: a refusal has a reason, and it is not blank.
    assert (
        "ALTER TABLE misstatement_version ADD CONSTRAINT ck_misstatement_version_refusal_reason "
        "CHECK ((state = 'refused') = (refusal_reason IS NOT NULL) AND "
        "(refusal_reason IS NULL OR length(trim(refusal_reason)) > 0))"
    ) in sql
    assert (
        "ALTER TABLE misstatement_version ADD CONSTRAINT "
        "ck_misstatement_version_withdrawal_reason CHECK ((state = 'withdrawn') = "
        "(withdrawal_reason IS NOT NULL) AND "
        "(withdrawal_reason IS NULL OR length(trim(withdrawal_reason)) > 0))"
    ) in sql
    # 0002 stays frozen: the new rules are not in its CREATE TABLE.
    assert "ck_misstatement_version_refusal_reason" not in table_block(sql, "misstatement_version")
    assert "CREATE FUNCTION oak_misstatements_version_transition() RETURNS trigger" in sql
    assert "previous.state = 'raised' AND NEW.state = 'communicated'" in sql
    assert "NEW.state IN ('corrected', 'refused', 'withdrawn')" in sql
    assert "NEW.version_no <> previous.version_no + 1" in sql
    assert (
        "CREATE TRIGGER trg_misstatement_version_transition BEFORE INSERT ON "
        "misstatement_version FOR EACH ROW "
        "EXECUTE FUNCTION oak_misstatements_version_transition()"
    ) in sql
    down = rendered("downgrade")
    assert "DROP TRIGGER IF EXISTS trg_misstatement_version_transition" in down
    assert "DROP FUNCTION IF EXISTS oak_misstatements_version_transition()" in down
    assert (
        "ALTER TABLE misstatement_version DROP CONSTRAINT ck_misstatement_version_refusal_reason"
        in down
    )
    assert down.index("DROP FUNCTION IF EXISTS oak_misstatements_version_transition()") < (
        down.index("DROP TABLE misstatement_version;")
    )


def test_no_migration_weakens_the_append_only_protection_of_the_record_tables() -> None:
    """D42: every record table gets its UPDATE/DELETE and TRUNCATE triggers when it is
    created, the function they call raises for every role, and no later migration drops a
    trigger, disables one, replaces the function, or grants the application role anything
    beyond SELECT and INSERT on them."""
    sql = rendered("upgrade")
    function = sql[sql.index("CREATE FUNCTION oak_misstatements_append_only()") :]
    function = function[: function.index("$$;") if "$$;" in function else 400]
    assert "RAISE EXCEPTION" in function and "TG_OP" in function
    assert not re.search(r"RETURN", function)  # it never lets a statement through
    assert sql.count("CREATE FUNCTION oak_misstatements_append_only()") == 1
    assert "CREATE OR REPLACE FUNCTION oak_misstatements_append_only" not in sql
    for table in ("misstatement", "misstatement_version", "misstatement_line_class", "event"):
        assert (
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
        ) in sql, table
        assert (
            f"CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
        ) in sql, table
        # Created after the table and never removed on the way up.
        assert sql.index(f"CREATE TRIGGER trg_{table}_append_only") > sql.index(
            f"CREATE TABLE {table} ("
        )
        assert f"DROP TRIGGER IF EXISTS trg_{table}_append_only" not in sql
        assert f"DROP TRIGGER IF EXISTS trg_{table}_no_truncate" not in sql
        assert f"ALTER TABLE {table} DISABLE" not in sql
        for line in sql.splitlines():
            granted = re.match(r"\s*GRANT (.+) ON (.+) TO oak_misstatements_app", line)
            if granted and table in [name.strip() for name in granted.group(2).split(",")]:
                assert granted.group(1).strip() == "SELECT, INSERT", line
    assert "DISABLE TRIGGER" not in sql
    assert "session_replication_role" not in sql
    assert "DROP FUNCTION IF EXISTS oak_misstatements_append_only" not in sql
    # 0007 adds rules; it removes none.
    tail = sql[sql.index("ck_misstatement_version_first_is_raised") :]
    assert "DROP " not in tail


def test_the_evaluation_row_is_append_only_and_its_aggregates_are_money_by_0008() -> None:
    sql = rendered("upgrade")
    block = table_block(sql, "evaluation")
    for column in ("agg_gross_pbt", "agg_net_pbt", "agg_gross_na", "agg_net_na"):
        assert f"ALTER TABLE evaluation ALTER COLUMN {column} TYPE money_amount" in sql, column
    for constraint in (
        "uq_evaluation_engagement_run",
        "ck_evaluation_run_positive",
        "ck_evaluation_gross_not_negative",
        "ck_evaluation_net_within_gross",
        "ck_evaluation_materiality_reassessed",
        "ck_evaluation_evaluated_by",
        "fk_evaluation_engagement",
        "fk_evaluation_threshold",
    ):
        assert constraint in block, constraint
    assert "abs(agg_net_pbt) <= agg_gross_pbt AND abs(agg_net_na) <= agg_gross_na" in block
    # No column for a line, a Dr, a Cr or one misstatement's effect.
    for forbidden in (" dr ", " cr ", "effect", "amount", "misstatement_id"):
        assert forbidden not in block, forbidden
    assert (
        "CREATE TRIGGER trg_evaluation_append_only BEFORE UPDATE OR DELETE ON evaluation "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_append_only()"
    ) in sql
    assert (
        "CREATE TRIGGER trg_evaluation_no_truncate BEFORE TRUNCATE ON evaluation "
        "FOR EACH STATEMENT EXECUTE FUNCTION oak_misstatements_append_only()"
    ) in sql
    assert "GRANT SELECT, INSERT ON evaluation TO oak_misstatements_app" in sql
    assert "UPDATE ON evaluation" not in sql and "DELETE ON evaluation TO" not in sql
    # A run is recorded against the engagement's own, current threshold version.
    assert "CREATE FUNCTION oak_misstatements_evaluation_threshold() RETURNS trigger" in sql
    assert "version.engagement_id <> NEW.engagement_id" in sql
    assert "version.superseded_by IS NOT NULL" in sql
    assert (
        "CREATE TRIGGER trg_evaluation_threshold BEFORE INSERT ON evaluation "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_evaluation_threshold()"
    ) in sql
    down = rendered("downgrade")
    assert "DROP TABLE evaluation;" in down
    assert "DROP FUNCTION IF EXISTS oak_misstatements_evaluation_threshold()" in down
    assert down.index("DROP TABLE evaluation;") < down.index("DROP TABLE threshold;")
    assert down.index("DROP TABLE evaluation;") < down.index(
        "ALTER TABLE misstatement_version DROP CONSTRAINT ck_misstatement_version_refusal_reason"
    )


def test_nothing_on_the_evaluation_table_would_refuse_a_later_added_column() -> None:
    """D44: the append-only protection is triggers on rows and on TRUNCATE. None is an event
    trigger, so migration 0009 could ADD COLUMN and ADD CONSTRAINT without touching a row or
    dropping the protection, and a later migration (``py_carried``) can do the same."""
    sql = rendered("upgrade")
    assert "CREATE EVENT TRIGGER" not in sql
    triggers = re.findall(r"CREATE TRIGGER (\w+) (BEFORE [A-Z ]+?) ON evaluation ", sql)
    assert triggers == [
        ("trg_evaluation_threshold", "BEFORE INSERT"),
        ("trg_evaluation_append_only", "BEFORE UPDATE OR DELETE"),
        ("trg_evaluation_no_truncate", "BEFORE TRUNCATE"),
        ("trg_evaluation_hard_gate", "BEFORE INSERT"),  # migration 0009
    ]
    # 0008 stays frozen: the conclusion columns are not in its CREATE TABLE.
    block = table_block(sql, "evaluation")
    for column in ("determination", "conclusion", "basis", "concluded_by", "py_carried"):
        assert column not in block, column
    assert "py_carried" not in sql


def test_the_conclusion_columns_and_the_hard_gate_are_added_by_0009() -> None:
    sql = rendered("upgrade")
    for column in ("determination", "conclusion", "basis", "concluded_by"):
        assert f"ALTER TABLE evaluation ADD COLUMN {column} TEXT;" in sql, column
    # Nullable, no default: existing runs are not rewritten and read as unconcluded.
    assert "ADD COLUMN conclusion TEXT NOT NULL" not in sql
    added = sql[sql.index("ALTER TABLE evaluation ADD COLUMN determination") :]
    assert "UPDATE evaluation" not in added and "DROP TRIGGER" not in added
    # Acceptance 10: all four present and the words not blank, or all four absent.
    assert (
        "ALTER TABLE evaluation ADD CONSTRAINT ck_evaluation_conclusion_complete CHECK ("
        "(determination IS NULL AND conclusion IS NULL AND basis IS NULL AND "
        "concluded_by IS NULL) OR (determination IS NOT NULL AND conclusion IS NOT NULL AND "
        "basis IS NOT NULL AND concluded_by IS NOT NULL AND length(trim(conclusion)) > 0 AND "
        "length(trim(basis)) > 0 AND length(trim(concluded_by)) > 0))"
    ) in sql
    assert (
        "ALTER TABLE evaluation ADD CONSTRAINT ck_evaluation_determination CHECK "
        "(determination IS NULL OR determination IN ('not_material', 'material'))"
    ) in sql
    assert (
        "ALTER TABLE evaluation ADD CONSTRAINT ck_evaluation_concluded_by_actor CHECK "
        "(concluded_by IS NULL OR concluded_by = evaluated_by)"
    ) in sql
    # Acceptance 7, as a gate at the database.
    assert "CREATE FUNCTION oak_misstatements_evaluation_hard_gate() RETURNS trigger" in sql
    assert "NEW.determination IS DISTINCT FROM 'not_material'" in sql
    assert "NEW.agg_gross_pbt >= overall OR NEW.agg_gross_na >= overall" in sql
    assert (
        "CREATE TRIGGER trg_evaluation_hard_gate BEFORE INSERT ON evaluation "
        "FOR EACH ROW EXECUTE FUNCTION oak_misstatements_evaluation_hard_gate()"
    ) in sql
    down = rendered("downgrade")
    assert "DROP TRIGGER IF EXISTS trg_evaluation_hard_gate ON evaluation" in down
    assert "DROP FUNCTION IF EXISTS oak_misstatements_evaluation_hard_gate()" in down
    assert "ALTER TABLE evaluation DROP COLUMN conclusion" in down
    assert down.index("ALTER TABLE evaluation DROP COLUMN conclusion") < down.index(
        "DROP TABLE evaluation;"
    )


def test_the_event_kinds_are_held_at_the_database_by_0010() -> None:
    from oak_misstatements.models.event import EVENT_KINDS

    sql = rendered("upgrade")
    listed = ", ".join(f"'{kind}'" for kind in EVENT_KINDS)
    assert f"ALTER TABLE event ADD CONSTRAINT ck_event_kind_known CHECK (kind IN ({listed}))" in sql
    # 0003 stays frozen, and the trail's append-only triggers are untouched.
    assert "ck_event_kind_known" not in table_block(sql, "event")
    tail = sql[sql.index("ck_event_kind_known") :]
    assert "DROP TRIGGER" not in tail and "UPDATE event" not in tail
    down = rendered("downgrade")
    assert "ALTER TABLE event DROP CONSTRAINT ck_event_kind_known" in down
    assert down.index("DROP CONSTRAINT ck_event_kind_known") < down.index("DROP TABLE event;")
