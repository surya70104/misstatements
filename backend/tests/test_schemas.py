"""Acceptance 1 at the request: a misstatement stored as a single amount cannot be created;
Dr/Cr lines are required and must balance. And spec 3.2's type-specific fields."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from oak_misstatements.schemas.misstatements import LineIn, MisstatementIn


def body(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "type": "factual",
        "description": "Rent for March not accrued",
        "raised_from": "wp",
        "source_ref": "E-4.2",
        "lines": [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}],
    }
    values.update(overrides)
    return values


def test_a_balanced_double_entry_is_accepted() -> None:
    request = MisstatementIn(**body())
    assert [line.to_spine() for line in request.lines] == [
        {"line_no": 5, "dr": "10000.00"},
        {"line_no": 3, "cr": "10000.00"},
    ]


def test_a_single_amount_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least 2 items"):
        MisstatementIn(**body(lines=[{"line_no": 5, "dr": "10000.00"}]))
    with pytest.raises(ValidationError):
        MisstatementIn(**body(lines=[]))


def test_unbalanced_lines_are_refused_naming_acceptance_1() -> None:
    with pytest.raises(ValidationError, match=r"must balance.*acceptance 1"):
        MisstatementIn(
            **body(lines=[{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "9999.99"}])
        )


def test_a_line_carries_exactly_one_side_above_zero() -> None:
    with pytest.raises(ValidationError, match="exactly one of dr and cr"):
        LineIn(line_no=5, dr="10", cr="10")
    with pytest.raises(ValidationError, match="exactly one of dr and cr"):
        LineIn(line_no=5)
    with pytest.raises(ValidationError, match="greater than 0"):
        LineIn(line_no=5, dr="0")
    with pytest.raises(ValidationError, match="greater than 0"):
        LineIn(line_no=5, cr="-5")
    with pytest.raises(ValidationError, match="decimal places"):
        LineIn(line_no=5, dr="1.005")


def test_a_line_names_an_import_ledger_or_introduces_one_never_both() -> None:
    with pytest.raises(ValidationError, match="must not also send a name"):
        LineIn(line_no=5, ledger_name="Rent", dr="1")
    with pytest.raises(ValidationError, match="ledger_name and head_id"):
        LineIn(ledger_name="Audit fee provision", dr="1")
    introduced = LineIn(
        ledger_name="Audit fee provision", head_id="bs.liabilities.current.provisions", cr="1"
    )
    assert introduced.to_spine() == {
        "ledger_name": "Audit fee provision",
        "parent_chain": [],
        "head_id": "bs.liabilities.current.provisions",
        "cr": "1",
    }


def test_the_same_import_ledger_appears_once() -> None:
    with pytest.raises(ValidationError, match="more than one line"):
        MisstatementIn(**body(lines=[{"line_no": 5, "dr": "10"}, {"line_no": 5, "cr": "10"}]))


def test_judgemental_needs_a_range_and_nothing_else_may_carry_one() -> None:
    with pytest.raises(ValidationError, match="carries range_low and range_high"):
        MisstatementIn(**body(type="judgemental"))
    with pytest.raises(ValidationError, match="range_low must not exceed"):
        MisstatementIn(**body(type="judgemental", range_low="20", range_high="10"))
    ok = MisstatementIn(**body(type="judgemental", range_low="5000", range_high="15000"))
    assert str(ok.range_high) == "15000"
    with pytest.raises(ValidationError, match="only a judgemental"):
        MisstatementIn(**body(range_low="1", range_high="2"))


def test_projected_needs_its_sample_and_basis_and_nothing_else_may_carry_them() -> None:
    with pytest.raises(ValidationError, match="sample_ref and projection_basis"):
        MisstatementIn(**body(type="projected"))
    # Since Pass 2 (D65) it says how it was projected too; the lines carry the amount.
    with pytest.raises(ValidationError, match="sampling_method"):
        MisstatementIn(**body(type="projected", sample_ref="S-7", projection_basis="ratio"))
    ok = MisstatementIn(
        **body(
            type="projected",
            sample_ref="S-7",
            projection_basis="ratio",
            sampling_method="ratio",
            population_value="1000000.00",
            population_size=500,
            sample_value="50000.00",
            sample_size=25,
            known_error_in_sample="500.00",
            projected_amount="10000.00",
        )
    )
    assert ok.sample_ref == "S-7"
    with pytest.raises(ValidationError, match="only a projected"):
        MisstatementIn(**body(sample_ref="S-7"))


def test_stage_1_sources_carry_a_working_paper_reference() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        MisstatementIn(**body(source_ref="   "))
    # Since Pass 2 (D64) a run is a source too, with its own attribution: a working
    # paper reference is not what it needs.
    with pytest.raises(ValidationError, match=r"run.run_id"):
        MisstatementIn(**body(raised_from="run"))
