"""Spec section 1: the module does not own a store of amounts. The only money columns on the
misstatement record are the judgemental range, which spec 3.2 puts there (D14, verification
D-4). The threshold table holds the three lines of spec section 4, which are limits, not
amounts of any misstatement. Dr, Cr, measures and effects live in the Financial Spine or are
computed on read."""

from __future__ import annotations

import re

from sqlalchemy import Numeric

from oak_misstatements.db import Base
from oak_misstatements.models import Engagement, Misstatement, MisstatementVersion  # noqa: F401

ALLOWED_MONEY = {
    ("misstatement_version", "range_low"),
    ("misstatement_version", "range_high"),
    # Spec section 4 and section 9 "threshold": the lines, the declared fraction and the PM
    # the Spine showed when they were set (D26).
    ("threshold", "om"),
    ("threshold", "pm"),
    ("threshold", "ctt"),
    ("threshold", "ctt_fraction"),
    ("threshold", "spine_pm_at_set"),
    # Spec section 9 "evaluation": the four aggregates of an evaluation run (D43). They are
    # sums over every uncorrected misstatement, the columns the spec's own data model
    # gives this table, and never one misstatement's Dr, Cr or effect.
    ("evaluation", "agg_gross_pbt"),
    ("evaluation", "agg_net_pbt"),
    ("evaluation", "agg_gross_na"),
    ("evaluation", "agg_net_na"),
}
AMOUNT_NAMES = re.compile(r"(^|_)(dr|cr|debit|credit|amount|measure|effect|total|balance)(_|$)")


def test_the_only_money_columns_are_the_judgemental_range() -> None:
    money = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Numeric)
    }
    assert money == ALLOWED_MONEY


def test_no_table_or_column_is_named_like_an_amount_or_a_line() -> None:
    assert "adjustment_line" not in Base.metadata.tables
    assert "line" not in Base.metadata.tables
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert not AMOUNT_NAMES.search(column.name), f"{table.name}.{column.name}"


def test_the_classification_snapshot_holds_labels_and_never_an_amount() -> None:
    table = Base.metadata.tables["misstatement_line_class"]
    assert not any(isinstance(column.type, Numeric) for column in table.columns)
    assert {column.name for column in table.columns} == {
        "id",
        "misstatement_version_id",
        "position",
        "ledger_key",
        "ledger_name",
        "parent_chain",
        "head_id",
        "nature",
        "head_item",
        "section",
        "spine_version_id",
        "tree_version",
        "created_at",
    }


def test_the_link_to_the_spine_is_mandatory_on_every_version() -> None:
    column = Base.metadata.tables["misstatement_version"].columns["spine_adjustment_id"]
    assert column.nullable is False


def test_the_evaluation_row_holds_aggregates_and_no_line_or_item_amount() -> None:
    table = Base.metadata.tables["evaluation"]
    money = {column.name for column in table.columns if isinstance(column.type, Numeric)}
    assert money == {"agg_gross_pbt", "agg_net_pbt", "agg_gross_na", "agg_net_na"}
    assert {column.name for column in table.columns} == {
        "id",
        "engagement_id",
        "run_no",
        "threshold_id",
        "agg_gross_pbt",
        "agg_net_pbt",
        "agg_gross_na",
        "agg_net_na",
        "materiality_reassessed",
        "detail",
        "evaluated_by",
        "determination",
        "conclusion",
        "basis",
        "concluded_by",
        "at",
    }
    for name in ("engagement_id", "threshold_id", "run_no", "evaluated_by", "detail"):
        assert table.columns[name].nullable is False, name
    # No foreign key reaches a misstatement: a run names them by reference, as labels.
    targets = {key.column.table.name for key in table.foreign_keys}
    assert targets == {"engagement", "threshold"}


def test_a_run_is_self_contained_and_holds_nothing_a_later_row_would_have_to_update() -> None:
    """D44, D45: a conclusion is a new row of this table carrying its own figures and
    threshold version, as spec section 9 draws it. That only stays append-only if no row
    ever needs changing when a later one arrives, so "latest", "current" and "stale" are
    computed on read and never stored, and no row points at another."""
    table = Base.metadata.tables["evaluation"]
    names = {column.name for column in table.columns}
    # Everything a conclusion must be tied to is on the row itself.
    assert {"engagement_id", "threshold_id", "agg_gross_pbt", "agg_net_pbt"} <= names
    assert {"agg_gross_na", "agg_net_na", "at"} <= names
    # The conclusion sits beside them (spec section 9), nullable: a run may conclude nothing.
    for name in ("determination", "conclusion", "basis", "concluded_by"):
        assert table.columns[name].nullable is True, name
    mutable = re.compile(r"(status|current|latest|stale|superseded|replaced|concluded$|is_)")
    assert not [name for name in names if mutable.search(name)]
    assert all(key.column.table.name != "evaluation" for key in table.foreign_keys)
    # The prior-period column is Pass 2 (B6) and is not here.
    assert "py_carried" not in names
