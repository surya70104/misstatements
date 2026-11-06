"""Migration 0002 applied to oak_misstatements_test: the rules that live in the database.
Skipped, visibly, until OAK_TEST_DATABASE_URL is set (pending decision O2)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.db


def seed(db: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    engagement_id = db.scalar(
        text("INSERT INTO engagement (label, created_by) VALUES ('FY26', 'test') RETURNING id")
    )
    misstatement_id = db.scalar(
        text(
            "INSERT INTO misstatement (engagement_id, ref_no, created_by) "
            "VALUES (:e, 1, 'test') RETURNING id"
        ),
        {"e": engagement_id},
    )
    version_id = db.scalar(
        text(
            "INSERT INTO misstatement_version (misstatement_id, version_no, type, description, "
            "raised_by, raised_from, source_ref, spine_adjustment_id, spine_kind, created_by) "
            "VALUES (:m, 1, 'factual', 'Rent', 'test', 'wp', 'E-4', :a, 'correction', 'test') "
            "RETURNING id"
        ),
        {"m": misstatement_id, "a": uuid.uuid4()},
    )
    assert engagement_id and misstatement_id and version_id
    return engagement_id, misstatement_id, version_id


def test_misstatement_and_its_versions_are_append_only_for_the_owner(db: Connection) -> None:
    _engagement, misstatement_id, version_id = seed(db)
    # Each refused statement runs in its own savepoint, so the seeded rows survive it. (The
    # first PostgreSQL run showed the earlier form rolled the rows back and then deleted
    # nothing, which no trigger can refuse.)
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(
            text("UPDATE misstatement_version SET description = 'x' WHERE id = :v"),
            {"v": version_id},
        )
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM misstatement_version WHERE id = :v"), {"v": version_id})
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM misstatement WHERE id = :m"), {"m": misstatement_id})
    assert db.scalar(text("SELECT count(*) FROM misstatement_version")) == 1
    assert db.scalar(text("SELECT count(*) FROM misstatement")) == 1


def test_the_application_role_cannot_update_or_delete_them(app_db: Connection) -> None:
    _engagement, _misstatement, version_id = seed(app_db)
    with pytest.raises(DBAPIError, match=r"permission denied|append-only"):
        app_db.execute(
            text("UPDATE misstatement_version SET state = 'communicated' WHERE id = :v"),
            {"v": version_id},
        )


def test_a_reference_is_unique_per_engagement(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    with pytest.raises(DBAPIError, match="uq_misstatement_engagement_ref"):
        db.execute(
            text(
                "INSERT INTO misstatement (engagement_id, ref_no, created_by) "
                "VALUES (:e, 1, 'test')"
            ),
            {"e": engagement_id},
        )


def test_type_specific_fields_are_enforced(db: Connection) -> None:
    _engagement, misstatement_id, _version = seed(db)
    with pytest.raises(DBAPIError, match="ck_misstatement_version_judgemental_range"):
        db.execute(
            text(
                "INSERT INTO misstatement_version (misstatement_id, version_no, type, description, "
                "raised_by, raised_from, source_ref, spine_adjustment_id, spine_kind, created_by) "
                "VALUES (:m, 2, 'judgemental', 'x', 't', 'wp', 'E', :a, 'correction', 't')"
            ),
            {"m": misstatement_id, "a": uuid.uuid4()},
        )


def test_money_columns_use_the_domain(db: Connection) -> None:
    _engagement, misstatement_id, _version = seed(db)
    with pytest.raises(DBAPIError, match="money_amount"):
        db.execute(
            text(
                "INSERT INTO misstatement_version (misstatement_id, version_no, type, description, "
                "raised_by, raised_from, source_ref, spine_adjustment_id, spine_kind, created_by, "
                "range_low, range_high) "
                "VALUES (:m, 2, 'judgemental', 'x', 't', 'wp', 'E', :a, 'correction', 't', "
                "1.005, 2)"
            ),
            {"m": misstatement_id, "a": uuid.uuid4()},
        )


# ---- Stage 2: threshold is superseded once and never deleted; event is append-only ------


INSERT_THRESHOLD = (
    "INSERT INTO threshold (id, engagement_id, version_no, om, pm, ctt, ctt_fraction, basis, "
    "set_by, spine_pm_status_at_set) "
    "VALUES (:id, :e, :v, :om, :pm, :ctt, :fraction, :basis, 'test', 'not_pinned') RETURNING id"
)


def seed_threshold(
    db: Connection,
    engagement_id: uuid.UUID,
    *,
    version_no: int = 1,
    pm: str = "250000",
    ctt: str = "12500",
    fraction: str = "0.05",
    threshold_id: uuid.UUID | None = None,
) -> uuid.UUID:
    written = db.scalar(
        text(INSERT_THRESHOLD),
        {
            "id": threshold_id or uuid.uuid4(),
            "e": engagement_id,
            "v": version_no,
            "om": "400000",
            "pm": pm,
            "ctt": ctt,
            "fraction": fraction,
            "basis": f"C-1 v{version_no}",
        },
    )
    assert written
    return uuid.UUID(str(written))


def test_a_threshold_version_changes_only_by_being_superseded_once(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    first = seed_threshold(db, engagement_id)
    # Any change but the supersession is refused.
    with pytest.raises(DBAPIError, match="only superseded_by may be set"), db.begin_nested():
        db.execute(text("UPDATE threshold SET pm = 1 WHERE id = :t"), {"t": first})
    # Two current versions for one engagement are refused, and so is a reused version number.
    with pytest.raises(DBAPIError, match="uq_threshold_current"), db.begin_nested():
        seed_threshold(db, engagement_id, version_no=2)
    with pytest.raises(DBAPIError, match="uq_threshold_engagement_version"), db.begin_nested():
        db.execute(
            text("UPDATE threshold SET superseded_by = :s WHERE id = :t"),
            {"t": first, "s": uuid.uuid4()},
        )
        seed_threshold(db, engagement_id, version_no=1)
    # The supersession itself: the old row points at the new id first (deferred foreign
    # key), then the new row is inserted as the only current one.
    second = uuid.uuid4()
    db.execute(
        text("UPDATE threshold SET superseded_by = :s WHERE id = :t"), {"t": first, "s": second}
    )
    seed_threshold(
        db,
        engagement_id,
        version_no=2,
        pm="200000",
        ctt="8000",
        fraction="0.04",
        threshold_id=second,
    )
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))  # the deferred successor check fires now
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM threshold WHERE engagement_id = :e AND superseded_by IS NULL"
            ),
            {"e": engagement_id},
        )
        == 1
    )
    # A superseded row is frozen for good, and nothing is ever deleted.
    with pytest.raises(DBAPIError, match="is superseded and cannot change"), db.begin_nested():
        db.execute(
            text("UPDATE threshold SET superseded_by = :s WHERE id = :t"),
            {"t": first, "s": uuid.uuid4()},
        )
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM threshold WHERE id = :t"), {"t": second})


def test_the_successor_must_be_a_later_version_of_the_same_engagement(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    other_engagement = db.scalar(
        text("INSERT INTO engagement (label, created_by) VALUES ('other', 'test') RETURNING id")
    )
    assert other_engagement
    first = seed_threshold(db, engagement_id)
    foreign = seed_threshold(db, uuid.UUID(str(other_engagement)))
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    with pytest.raises(DBAPIError, match="belongs to another engagement"), db.begin_nested():
        db.execute(
            text("UPDATE threshold SET superseded_by = :s WHERE id = :t"),
            {"t": first, "s": foreign},
        )
    # A successor that does not exist: the foreign key refuses it. PostgreSQL fires the
    # key's own check before the constraint trigger, so the trigger's message for this case
    # is never the one seen; either refusal is the rule holding.
    with (
        pytest.raises(DBAPIError, match=r"fk_threshold_superseded_by|does not exist"),
        db.begin_nested(),
    ):
        db.execute(
            text("UPDATE threshold SET superseded_by = :s WHERE id = :t"),
            {"t": first, "s": uuid.uuid4()},
        )
    # A second version can only exist once the first is superseded by it (one current
    # version per engagement), so supersede properly first: with the checks deferred, point
    # version 1 at version 2, insert version 2, then make every check run.
    second = uuid.uuid4()
    db.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db.execute(
        text("UPDATE threshold SET superseded_by = :s WHERE id = :t"), {"t": first, "s": second}
    )
    seed_threshold(db, engagement_id, version_no=2, threshold_id=second)
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))  # the valid supersession passes
    # A successor with a lower number is refused: point version 2 back at version 1.
    with pytest.raises(DBAPIError, match="not a later version"), db.begin_nested():
        db.execute(
            text("UPDATE threshold SET superseded_by = :s WHERE id = :t"),
            {"t": second, "s": first},
        )


def test_the_stored_ctt_must_equal_pm_times_the_fraction_to_the_paisa(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    with pytest.raises(DBAPIError, match="ck_threshold_ctt_consistent"), db.begin_nested():
        seed_threshold(db, engagement_id, pm="250000", ctt="12000", fraction="0.05")
    # Half up, as the application rounds: 333333.33 * 0.05 = 16666.6665 -> 16666.67.
    with pytest.raises(DBAPIError, match="ck_threshold_ctt_consistent"), db.begin_nested():
        seed_threshold(db, engagement_id, pm="333333.33", ctt="16666.66", fraction="0.05")
    seed_threshold(db, engagement_id, pm="333333.33", ctt="16666.67", fraction="0.05")


def test_the_spine_pm_status_and_amount_agree_at_the_database(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    with (
        pytest.raises(DBAPIError, match="ck_threshold_spine_pm_amount_matches_status"),
        db.begin_nested(),
    ):
        db.execute(
            text(
                "INSERT INTO threshold (engagement_id, version_no, om, pm, ctt, ctt_fraction, "
                "basis, set_by, spine_version_id, spine_pm_status_at_set) "
                "VALUES (:e, 1, 400000, 250000, 12500, 0.05, 'C-1', 'test', :v, 'available')"
            ),
            {"e": engagement_id, "v": uuid.uuid4()},
        )
    with (
        pytest.raises(DBAPIError, match="ck_threshold_spine_pm_pinned_matches_status"),
        db.begin_nested(),
    ):
        db.execute(
            text(
                "INSERT INTO threshold (engagement_id, version_no, om, pm, ctt, ctt_fraction, "
                "basis, set_by, spine_pm_status_at_set) "
                "VALUES (:e, 1, 400000, 250000, 12500, 0.05, 'C-1', 'test', 'unreachable')"
            ),
            {"e": engagement_id},
        )


def test_the_application_role_may_set_superseded_by_and_nothing_else(app_db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(app_db)
    first = seed_threshold(app_db, engagement_id)
    with pytest.raises(DBAPIError, match="permission denied"), app_db.begin_nested():
        app_db.execute(text("UPDATE threshold SET basis = 'x' WHERE id = :t"), {"t": first})
    with pytest.raises(DBAPIError, match=r"permission denied|append-only"), app_db.begin_nested():
        app_db.execute(text("DELETE FROM threshold WHERE id = :t"), {"t": first})


def test_event_is_append_only_for_the_owner(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    event_id = db.scalar(
        text(
            "INSERT INTO event (engagement_id, kind, payload, actor) "
            "VALUES (:e, 'threshold_recompute', '{}'::jsonb, 'test') RETURNING id"
        ),
        {"e": engagement_id},
    )
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE event SET actor = 'x' WHERE id = :v"), {"v": event_id})


def test_the_classification_snapshot_is_append_only_for_the_owner(db: Connection) -> None:
    _engagement, _misstatement, version_id = seed(db)
    row_id = db.scalar(
        text(
            "INSERT INTO misstatement_line_class (misstatement_version_id, position, ledger_key, "
            "ledger_name, parent_chain, head_id, nature, section, spine_version_id) "
            "VALUES (:v, 1, 'rent', 'Rent', '[]'::jsonb, 'pl.expenses.other', 'PL', "
            "'pl_before_tax', :s) RETURNING id"
        ),
        {"v": version_id, "s": uuid.uuid4()},
    )
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(
            text("UPDATE misstatement_line_class SET section = 'equity' WHERE id = :r"),
            {"r": row_id},
        )
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM misstatement_line_class WHERE id = :r"), {"r": row_id})
    with pytest.raises(DBAPIError, match="uq_line_class_position"), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO misstatement_line_class (misstatement_version_id, position, "
                "ledger_key, ledger_name, parent_chain, section, spine_version_id) "
                "VALUES (:v, 1, 'x', 'X', '[]'::jsonb, 'assets', :s)"
            ),
            {"v": version_id, "s": uuid.uuid4()},
        )


def test_pm_at_or_above_om_is_refused_by_the_database(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    # Each row is right in every other respect (CTT is PM times the fraction), so the only
    # rule it breaks is the one under test.
    for pm, ctt in (("400000", "20000"), ("500000", "25000")):
        with pytest.raises(DBAPIError, match="ck_threshold_pm_below_om"), db.begin_nested():
            db.execute(
                text(INSERT_THRESHOLD),
                {
                    "id": uuid.uuid4(),
                    "e": engagement_id,
                    "v": 1,
                    "om": "400000",
                    "pm": pm,
                    "ctt": ctt,
                    "fraction": "0.05",
                    "basis": "C-1",
                },
            )
    seed_threshold(db, engagement_id, pm="399999.99", ctt="20000.00", fraction="0.05")


def test_the_engagement_audit_columns_cannot_be_rewritten(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    for statement in (
        "UPDATE engagement SET created_by = 'someone else' WHERE id = :e",
        "UPDATE engagement SET label = 'renamed' WHERE id = :e",
        "UPDATE engagement SET created_at = now() - interval '1 day' WHERE id = :e",
    ):
        with pytest.raises(DBAPIError, match="only the Spine link may change"), db.begin_nested():
            db.execute(text(statement), {"e": engagement_id})
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM engagement WHERE id = :e"), {"e": engagement_id})
    # The link itself may still be set.
    db.execute(
        text("UPDATE engagement SET spine_engagement_id = :s WHERE id = :e"),
        {"e": engagement_id, "s": uuid.uuid4()},
    )


def test_the_application_role_may_update_only_the_engagement_link(app_db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(app_db)
    with pytest.raises(DBAPIError, match="permission denied"), app_db.begin_nested():
        app_db.execute(
            text("UPDATE engagement SET created_by = 'x' WHERE id = :e"), {"e": engagement_id}
        )
    app_db.execute(
        text("UPDATE engagement SET spine_engagement_id = :s WHERE id = :e"),
        {"e": engagement_id, "s": uuid.uuid4()},
    )


# ---- Stage 3 (migration 0007): the state machine at the database ---------------------------

NEXT_VERSION = (
    "INSERT INTO misstatement_version (misstatement_id, version_no, type, description, "
    "raised_by, raised_from, source_ref, spine_adjustment_id, spine_kind, created_by, state, "
    "communicated_at, decided_at, refusal_reason, withdrawal_reason) "
    "VALUES (:m, :n, 'factual', 'Rent', 'test', 'wp', 'E-4', :a, 'correction', 'test', :s, "
    ":c, :d, :r, :w)"
)


def insert_version(
    db: Connection, misstatement_id: uuid.UUID, number: int, state: str, **extra: object
) -> None:
    values: dict[str, object] = {
        "m": misstatement_id,
        "n": number,
        "a": uuid.uuid4(),
        "s": state,
        "c": None if state == "raised" else "2026-11-05T10:00:00+00:00",
        "d": "2026-11-05T11:00:00+00:00"
        if state in ("corrected", "refused", "withdrawn")
        else None,
        "r": "management disagrees" if state == "refused" else None,
        "w": "raised in error" if state == "withdrawn" else None,
    }
    values.update(extra)
    db.execute(text(NEXT_VERSION), values)


def test_the_database_allows_exactly_the_moves_of_the_diagram(db: Connection) -> None:
    _engagement, misstatement_id, _version = seed(db)
    for state in ("corrected", "refused", "withdrawn"):
        with pytest.raises(DBAPIError, match="not a move of the state machine"), db.begin_nested():
            insert_version(db, misstatement_id, 2, state)
    with pytest.raises(DBAPIError, match="does not follow version"), db.begin_nested():
        insert_version(db, misstatement_id, 3, "communicated")
    insert_version(db, misstatement_id, 2, "communicated")
    with pytest.raises(DBAPIError, match="not a move of the state machine"), db.begin_nested():
        insert_version(db, misstatement_id, 3, "raised")
    insert_version(db, misstatement_id, 3, "refused")
    for state in ("communicated", "corrected", "refused", "withdrawn"):
        with pytest.raises(DBAPIError, match="not a move of the state machine"), db.begin_nested():
            insert_version(db, misstatement_id, 4, state)


def test_the_first_version_is_version_one_and_raised(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    other = db.scalar(
        text(
            "INSERT INTO misstatement (engagement_id, ref_no, created_by) "
            "VALUES (:e, 2, 'test') RETURNING id"
        ),
        {"e": engagement_id},
    )
    assert other is not None
    with pytest.raises(DBAPIError, match="the first version is version 1"), db.begin_nested():
        insert_version(db, other, 1, "communicated")
    with pytest.raises(DBAPIError, match="the first version is version 1"), db.begin_nested():
        insert_version(db, other, 2, "raised")


def test_the_dates_and_reasons_follow_the_state_at_the_database(db: Connection) -> None:
    _engagement, misstatement_id, _version = seed(db)
    with (
        pytest.raises(DBAPIError, match="ck_misstatement_version_communicated_at"),
        db.begin_nested(),
    ):
        insert_version(db, misstatement_id, 2, "communicated", c=None)
    insert_version(db, misstatement_id, 2, "communicated")
    with (
        pytest.raises(DBAPIError, match="ck_misstatement_version_refusal_reason"),
        db.begin_nested(),
    ):
        insert_version(db, misstatement_id, 3, "refused", r=None)  # acceptance 3
    with (
        pytest.raises(DBAPIError, match="ck_misstatement_version_refusal_reason"),
        db.begin_nested(),
    ):
        insert_version(db, misstatement_id, 3, "refused", r="   ")
    with (
        pytest.raises(DBAPIError, match="ck_misstatement_version_withdrawal_reason"),
        db.begin_nested(),
    ):
        insert_version(db, misstatement_id, 3, "withdrawn", w=None)
    with pytest.raises(DBAPIError, match="ck_misstatement_version_decided_at"), db.begin_nested():
        insert_version(db, misstatement_id, 3, "corrected", d=None)
    with (
        pytest.raises(DBAPIError, match="ck_misstatement_version_refusal_reason"),
        db.begin_nested(),
    ):
        insert_version(db, misstatement_id, 3, "corrected", r="a reason on a correction")
    insert_version(db, misstatement_id, 3, "withdrawn")


# ---- D42: history and the lock, on PostgreSQL -------------------------------------------------


def test_no_role_can_change_or_delete_a_version_after_a_move(db: Connection) -> None:
    _engagement, misstatement_id, version_id = seed(db)
    insert_version(db, misstatement_id, 2, "communicated")
    insert_version(db, misstatement_id, 3, "refused")
    for statement in (
        "UPDATE misstatement_version SET state = 'raised' WHERE id = :v",
        "UPDATE misstatement_version SET refusal_reason = 'rewritten' WHERE misstatement_id = :m",
        "UPDATE misstatement_version SET decided_at = now() WHERE misstatement_id = :m",
        "DELETE FROM misstatement_version WHERE id = :v",
        "DELETE FROM misstatement_version WHERE misstatement_id = :m",
        "DELETE FROM misstatement WHERE id = :m",
    ):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement), {"v": version_id, "m": misstatement_id})
    # A plain TRUNCATE of a table another table references is refused by PostgreSQL itself,
    # before any trigger. With CASCADE that refusal is gone, and the triggers must hold.
    with (
        pytest.raises(DBAPIError, match=r"append-only|cannot truncate a table referenced"),
        db.begin_nested(),
    ):
        db.execute(text("TRUNCATE misstatement_version"))
    for statement in (
        "TRUNCATE misstatement_version CASCADE",
        "TRUNCATE misstatement CASCADE",
        "TRUNCATE misstatement_line_class",
        "TRUNCATE engagement CASCADE",
    ):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement))
    assert db.scalar(text("SELECT count(*) FROM misstatement_version")) == 3
    assert db.scalar(text("SELECT count(*) FROM misstatement")) == 1


def test_the_application_role_can_lock_the_engagement_row_but_change_no_version(
    app_db: Connection,
) -> None:
    engagement_id, misstatement_id, version_id = seed(app_db)
    # The row lock every move takes: column-level UPDATE on the link columns is enough.
    locked = app_db.scalar(
        text("SELECT id FROM engagement WHERE id = :e FOR UPDATE"), {"e": engagement_id}
    )
    assert locked == engagement_id
    insert_version(app_db, misstatement_id, 2, "communicated")
    for statement in (
        "UPDATE misstatement_version SET state = 'corrected' WHERE id = :v",
        "DELETE FROM misstatement_version WHERE id = :v",
    ):
        with (
            pytest.raises(DBAPIError, match=r"permission denied|append-only"),
            app_db.begin_nested(),
        ):
            app_db.execute(text(statement), {"v": version_id})


def test_two_versions_cannot_take_the_same_number(db: Connection) -> None:
    _engagement, misstatement_id, _version = seed(db)
    insert_version(db, misstatement_id, 2, "communicated")
    with (
        pytest.raises(DBAPIError, match=r"does not follow|uq_misstatement_version_no"),
        db.begin_nested(),
    ):
        insert_version(db, misstatement_id, 2, "communicated")


# ---- Stage 4 (migration 0008): the evaluation row -------------------------------------------

EVALUATION = (
    "INSERT INTO evaluation (engagement_id, run_no, threshold_id, agg_gross_pbt, agg_net_pbt, "
    "agg_gross_na, agg_net_na, materiality_reassessed, detail, evaluated_by) "
    "VALUES (:e, :n, :t, :gp, :np, :gn, :nn, :r, '{}'::jsonb, :by) RETURNING id"
)


def evaluation_values(
    engagement_id: uuid.UUID, threshold_id: object, **extra: object
) -> dict[str, object]:
    values: dict[str, object] = {
        "e": engagement_id,
        "n": 1,
        "t": threshold_id,
        "gp": "100.00",
        "np": "-100.00",
        "gn": "100.00",
        "nn": "-100.00",
        "r": True,
        "by": "test",
    }
    values.update(extra)
    return values


def test_an_evaluation_run_is_append_only_for_every_role(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    threshold_id = seed_threshold(db, engagement_id)
    run_id = db.scalar(text(EVALUATION), evaluation_values(engagement_id, threshold_id))
    for statement in (
        "UPDATE evaluation SET agg_gross_pbt = 0 WHERE id = :r",
        "UPDATE evaluation SET evaluated_by = 'someone else' WHERE id = :r",
        "DELETE FROM evaluation WHERE id = :r",
    ):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement), {"r": run_id})
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("TRUNCATE evaluation"))


def test_the_evaluation_aggregates_are_checked_at_the_database(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    threshold_id = seed_threshold(db, engagement_id)
    for extra, rule in (
        ({"gp": "-1.00", "np": "0.00"}, "ck_evaluation_gross_not_negative"),
        ({"gp": "100.00", "np": "-100.01"}, "ck_evaluation_net_within_gross"),
        ({"gn": "50.00", "nn": "60.00"}, "ck_evaluation_net_within_gross"),
        ({"r": False}, "ck_evaluation_materiality_reassessed"),
        ({"by": "  "}, "ck_evaluation_evaluated_by"),
        ({"n": 0}, "ck_evaluation_run_positive"),
        ({"gp": "100.005", "np": "0.00"}, "money_amount"),
    ):
        with pytest.raises(DBAPIError, match=rule), db.begin_nested():
            db.execute(text(EVALUATION), evaluation_values(engagement_id, threshold_id, **extra))
    db.execute(text(EVALUATION), evaluation_values(engagement_id, threshold_id))
    with pytest.raises(DBAPIError, match="uq_evaluation_engagement_run"), db.begin_nested():
        db.execute(text(EVALUATION), evaluation_values(engagement_id, threshold_id))


def test_a_run_is_recorded_only_against_the_engagements_current_threshold(
    db: Connection,
) -> None:
    engagement_id, _misstatement, _version = seed(db)
    other = db.scalar(
        text("INSERT INTO engagement (label, created_by) VALUES ('other', 'test') RETURNING id")
    )
    assert other is not None
    foreign = seed_threshold(db, other)
    with pytest.raises(DBAPIError, match="belongs to another engagement"), db.begin_nested():
        db.execute(text(EVALUATION), evaluation_values(engagement_id, foreign))
    with pytest.raises(DBAPIError, match="does not exist"), db.begin_nested():
        db.execute(text(EVALUATION), evaluation_values(engagement_id, uuid.uuid4()))
    first = seed_threshold(db, engagement_id)
    second = uuid.uuid4()
    db.execute(
        text("UPDATE threshold SET superseded_by = :s WHERE id = :f"), {"s": second, "f": first}
    )
    seed_threshold(db, engagement_id, version_no=2, threshold_id=second)
    with pytest.raises(DBAPIError, match="is superseded"), db.begin_nested():
        db.execute(text(EVALUATION), evaluation_values(engagement_id, first))
    db.execute(text(EVALUATION), evaluation_values(engagement_id, second))


def test_the_application_role_may_insert_a_run_and_nothing_else(app_db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(app_db)
    threshold_id = seed_threshold(app_db, engagement_id)
    run_id = app_db.scalar(text(EVALUATION), evaluation_values(engagement_id, threshold_id))
    for statement in (
        "UPDATE evaluation SET agg_net_pbt = 0 WHERE id = :r",
        "DELETE FROM evaluation WHERE id = :r",
    ):
        with (
            pytest.raises(DBAPIError, match=r"permission denied|append-only"),
            app_db.begin_nested(),
        ):
            app_db.execute(text(statement), {"r": run_id})


# ---- Stage 5 (migration 0009): the conclusion on the evaluation row -------------------------

CONCLUDED = (
    "INSERT INTO evaluation (engagement_id, run_no, threshold_id, agg_gross_pbt, agg_net_pbt, "
    "agg_gross_na, agg_net_na, materiality_reassessed, detail, evaluated_by, determination, "
    "conclusion, basis, concluded_by) "
    "VALUES (:e, :n, :t, :gp, :np, :gn, :nn, true, '{}'::jsonb, :by, :d, :c, :b, :cb) "
    "RETURNING id"
)


def concluded_values(
    engagement_id: uuid.UUID, threshold_id: object, **extra: object
) -> dict[str, object]:
    values: dict[str, object] = {
        "e": engagement_id,
        "n": 1,
        "t": threshold_id,
        "gp": "100.00",
        "np": "-100.00",
        "gn": "100.00",
        "nn": "-100.00",
        "by": "partner@firm",
        "d": "not_material",
        "c": "Not material.",
        "b": "Below PM; see C-4.",
        "cb": "partner@firm",
    }
    values.update(extra)
    return values


def test_a_conclusion_is_complete_or_absent_at_the_database(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    threshold_id = seed_threshold(db, engagement_id)
    for extra, rule in (
        ({"c": None}, "ck_evaluation_conclusion_complete"),  # acceptance 10
        ({"c": "   "}, "ck_evaluation_conclusion_complete"),
        ({"b": None}, "ck_evaluation_conclusion_complete"),
        ({"b": ""}, "ck_evaluation_conclusion_complete"),
        ({"cb": None}, "ck_evaluation_conclusion_complete"),
        ({"d": None}, "ck_evaluation_conclusion_complete"),
        ({"d": "immaterial"}, "ck_evaluation_determination"),
        ({"cb": "someone-else@firm"}, "ck_evaluation_concluded_by_actor"),
    ):
        with pytest.raises(DBAPIError, match=rule), db.begin_nested():
            db.execute(text(CONCLUDED), concluded_values(engagement_id, threshold_id, **extra))
    db.execute(text(CONCLUDED), concluded_values(engagement_id, threshold_id))
    # A run that concludes nothing is still accepted.
    db.execute(
        text(CONCLUDED),
        concluded_values(engagement_id, threshold_id, n=2, d=None, c=None, b=None, cb=None),
    )


def test_acceptance_7_the_hard_gate_refuses_not_material_at_the_database(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    threshold_id = seed_threshold(db, engagement_id)  # OM 400,000
    at_om = {"gp": "400000.00", "np": "-400000.00"}
    on_net_assets = {"gn": "400000.00", "nn": "400000.00"}
    for extra in (at_om, on_net_assets, {"gp": "400000.01", "np": "0.00"}):
        with pytest.raises(DBAPIError, match="not material refused"), db.begin_nested():
            db.execute(text(CONCLUDED), concluded_values(engagement_id, threshold_id, **extra))
    # A paisa below is accepted; so is concluding that it is material, and a plain run.
    db.execute(
        text(CONCLUDED),
        concluded_values(engagement_id, threshold_id, gp="399999.99", np="-399999.99"),
    )
    db.execute(
        text(CONCLUDED), concluded_values(engagement_id, threshold_id, n=2, d="material", **at_om)
    )
    db.execute(
        text(CONCLUDED),
        concluded_values(
            engagement_id, threshold_id, n=3, d=None, c=None, b=None, cb=None, **at_om
        ),
    )


def test_a_conclusion_can_never_be_added_to_or_removed_from_a_row(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    threshold_id = seed_threshold(db, engagement_id)
    plain = db.scalar(
        text(CONCLUDED),
        concluded_values(engagement_id, threshold_id, d=None, c=None, b=None, cb=None),
    )
    concluded = db.scalar(text(CONCLUDED), concluded_values(engagement_id, threshold_id, n=2))
    for statement, row in (
        (
            "UPDATE evaluation SET determination = 'not_material', conclusion = 'x', basis = 'x', "
            "concluded_by = evaluated_by WHERE id = :r",
            plain,
        ),
        ("UPDATE evaluation SET conclusion = 'rewritten' WHERE id = :r", concluded),
        ("UPDATE evaluation SET determination = 'material' WHERE id = :r", concluded),
        ("DELETE FROM evaluation WHERE id = :r", concluded),
    ):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement), {"r": row})


# ---- D46 (migration 0010): only the module's own event kinds ------------------------------


def test_an_event_of_an_unknown_kind_is_refused_by_the_database(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    insert = (
        "INSERT INTO event (engagement_id, kind, payload, actor) "
        "VALUES (:e, :k, '{}'::jsonb, 'test')"
    )
    for kind in ("partner_approved", "THRESHOLD_RECOMPUTE", "x"):
        with pytest.raises(DBAPIError, match="ck_event_kind_known"), db.begin_nested():
            db.execute(text(insert), {"e": engagement_id, "k": kind})
    for kind in (
        "threshold_recompute",
        "soft_gate_acknowledged",
        "materiality_reassessed",
        "evaluation_concluded",
        "strategy_trigger_response",
    ):
        db.execute(text(insert), {"e": engagement_id, "k": kind})


# ---- Pass 2 (migration 0012): the prior-period carry-forward (architecture D61) --------------

PRIOR_PERIOD = (
    "INSERT INTO prior_period (engagement_id, ref, version_no, carried, description, "
    "prior_period, source_ref, source_misstatement_id, prior_profit, prior_net_assets, "
    "current_profit, current_net_assets, cumulative_profit, cumulative_net_assets, basis, "
    "recorded_by) "
    "VALUES (:e, :ref, :v, :carried, :d, :p, :s, :m, :pp, :pn, :cp, :cn, :mp, :mn, :b, :by) "
    "RETURNING id"
)


def prior_period_values(engagement_id: uuid.UUID, **extra: object) -> dict[str, object]:
    values: dict[str, object] = {
        "e": engagement_id,
        "ref": "PY-1",
        "v": 1,
        "carried": True,
        "d": "Depreciation understated in the prior year",
        "p": "FY 2024-25",
        "s": "PY schedule M-7",
        "m": None,
        "pp": None,
        "pn": None,
        "cp": "0.00",
        "cn": "-30000.00",
        "mp": "-30000.00",
        "mn": "-30000.00",
        "b": "Still stands at the year end",
        "by": "test",
    }
    values.update(extra)
    return values


def test_a_prior_period_version_is_append_only_for_the_owner(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    row_id = db.scalar(text(PRIOR_PERIOD), prior_period_values(engagement_id))
    for statement in (
        "UPDATE prior_period SET cumulative_net_assets = 0 WHERE id = :r",
        "UPDATE prior_period SET carried = false WHERE id = :r",
        "UPDATE prior_period SET basis = 'rewritten' WHERE id = :r",
        "DELETE FROM prior_period WHERE id = :r",
    ):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement), {"r": row_id})
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("TRUNCATE prior_period"))
    assert db.scalar(text("SELECT count(*) FROM prior_period")) == 1
    # A revision and a removal are further versions of the same item.
    db.execute(text(PRIOR_PERIOD), prior_period_values(engagement_id, v=2, mn="-25000.00"))
    db.execute(text(PRIOR_PERIOD), prior_period_values(engagement_id, v=3, carried=False))
    assert db.scalar(text("SELECT count(*) FROM prior_period")) == 3


def test_the_prior_period_rules_are_checked_at_the_database(db: Connection) -> None:
    engagement_id, misstatement_id, _version = seed(db)
    for extra, rule in (
        ({"b": "   "}, "ck_prior_period_basis_not_blank"),
        ({"d": ""}, "ck_prior_period_description"),
        ({"p": " "}, "ck_prior_period_period"),
        ({"s": ""}, "ck_prior_period_source_ref"),
        ({"by": " "}, "ck_prior_period_recorded_by"),
        ({"v": 0}, "ck_prior_period_version_positive"),
        # Money, to the paisa and no further.
        ({"cp": "100.005"}, "money_amount"),
        ({"mn": "-0.001"}, "money_amount"),
        # Rolled forward: the link and both effects there, or none of the three.
        ({"m": misstatement_id}, "ck_prior_period_source_complete"),
        ({"pp": "-60000.00", "pn": "-60000.00"}, "ck_prior_period_source_complete"),
        ({"m": misstatement_id, "pp": "-60000.00"}, "ck_prior_period_source_complete"),
        ({"m": uuid.uuid4(), "pp": "1.00", "pn": "1.00"}, "fk_prior_period_source_misstatement"),
        ({"e": uuid.uuid4()}, "fk_prior_period_engagement"),
    ):
        with pytest.raises(DBAPIError, match=rule), db.begin_nested():
            db.execute(text(PRIOR_PERIOD), prior_period_values(engagement_id, **extra))
    db.execute(
        text(PRIOR_PERIOD),
        prior_period_values(engagement_id, m=misstatement_id, pp="-60000.00", pn="-60000.00"),
    )
    with pytest.raises(DBAPIError, match="uq_prior_period_version"), db.begin_nested():
        db.execute(text(PRIOR_PERIOD), prior_period_values(engagement_id))
    # The misstatement it was rolled forward from can never be deleted from under it.
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM misstatement WHERE id = :m"), {"m": misstatement_id})


def test_the_application_role_may_insert_a_prior_period_version_and_nothing_else(
    app_db: Connection,
) -> None:
    engagement_id, _misstatement, _version = seed(app_db)
    row_id = app_db.scalar(text(PRIOR_PERIOD), prior_period_values(engagement_id))
    assert app_db.scalar(text("SELECT count(*) FROM prior_period")) == 1
    for statement in (
        "UPDATE prior_period SET carried = false WHERE id = :r",
        "DELETE FROM prior_period WHERE id = :r",
    ):
        with (
            pytest.raises(DBAPIError, match=r"permission denied|append-only"),
            app_db.begin_nested(),
        ):
            app_db.execute(text(statement), {"r": row_id})


WITH_PY_CARRIED = (
    "INSERT INTO evaluation (engagement_id, run_no, threshold_id, agg_gross_pbt, agg_net_pbt, "
    "agg_gross_na, agg_net_na, materiality_reassessed, detail, evaluated_by, py_carried) "
    "VALUES (:e, :n, :t, :gp, :np, :gn, :nn, :r, '{}'::jsonb, :by, CAST(:py AS jsonb)) "
    "RETURNING id"
)


def test_py_carried_is_recorded_with_a_run_and_can_never_be_changed(db: Connection) -> None:
    engagement_id, _misstatement, _version = seed(db)
    threshold_id = seed_threshold(db, engagement_id)
    # A run written as before migration 0012 has none.
    earlier = db.scalar(text(EVALUATION), evaluation_values(engagement_id, threshold_id))
    assert (
        db.scalar(text("SELECT py_carried FROM evaluation WHERE id = :r"), {"r": earlier}) is None
    )
    carried = '{"items": [{"ref": "PY-1", "version_no": 1}]}'
    run_id = db.scalar(
        text(WITH_PY_CARRIED), evaluation_values(engagement_id, threshold_id, n=2, py=carried)
    )
    assert db.scalar(text("SELECT py_carried FROM evaluation WHERE id = :r"), {"r": run_id}) == {
        "items": [{"ref": "PY-1", "version_no": 1}]
    }
    for target in (earlier, run_id):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(
                text("UPDATE evaluation SET py_carried = '{}'::jsonb WHERE id = :r"), {"r": target}
            )
