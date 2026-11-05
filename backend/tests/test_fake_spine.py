"""The double keeps the Spine's rules the module depends on (D11), each cited in
``tests/fake_spine.py``: decided once, frozen when locked, posted only when accepted."""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx

from tests.fake_spine import LOCKED_VERSION_ID, OPEN_VERSION_ID, FakeSpine

LINES = [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}]


def propose(
    double: FakeSpine, lines: list[dict[str, object]] = LINES, **extra: object
) -> httpx.Response:
    body: dict[str, object] = {
        "kind": "correction",
        "narration": "Rent not accrued",
        "working_paper_ref": "E-4.2",
        "lines": lines,
    }
    body.update(extra)
    return double.handle(
        httpx.Request(
            "POST", f"http://spine.test/api/spine-versions/{OPEN_VERSION_ID}/adjustments", json=body
        )
    )


def decide(
    double: FakeSpine, adjustment_id: str, status: str, version: uuid.UUID = OPEN_VERSION_ID
) -> httpx.Response:
    return double.handle(
        httpx.Request(
            "POST",
            f"http://spine.test/api/spine-versions/{version}/adjustments/{adjustment_id}/decision",
            json={"status": status, "note": None},
        )
    )


def test_only_an_accepted_adjustment_moves_the_adjusted_balance() -> None:
    double = FakeSpine()
    before = double.adjusted_balance(OPEN_VERSION_ID, "Rent")
    answer = propose(double)
    assert answer.status_code == 201
    adjustment_id = answer.json()["adjustment_id"]
    assert double.adjusted_balance(OPEN_VERSION_ID, "Rent") == before  # proposed: not posted
    refused = FakeSpine()
    other = propose(refused).json()["adjustment_id"]
    assert decide(refused, other, "refused").status_code == 200
    assert refused.adjusted_balance(OPEN_VERSION_ID, "Rent") == before  # refused: not posted
    assert decide(double, adjustment_id, "accepted").status_code == 200
    assert double.adjusted_balance(OPEN_VERSION_ID, "Rent") == before + Decimal("10000.00")
    assert double.adjusted_balance(OPEN_VERSION_ID, "Provision for expenses") == Decimal(
        "-90000.00"
    )


def test_an_adjustment_is_decided_once() -> None:
    double = FakeSpine()
    adjustment_id = propose(double).json()["adjustment_id"]
    assert decide(double, adjustment_id, "accepted").status_code == 200
    again = decide(double, adjustment_id, "refused")
    assert again.status_code == 409
    assert "cannot be changed" in again.json()["detail"]["message"]


def test_a_locked_version_takes_nothing() -> None:
    double = FakeSpine()
    locked = double.handle(
        httpx.Request(
            "POST",
            f"http://spine.test/api/spine-versions/{LOCKED_VERSION_ID}/adjustments",
            json={"kind": "correction", "narration": "x", "working_paper_ref": "y", "lines": LINES},
        )
    )
    assert locked.status_code == 409
    assert locked.json()["detail"]["code"] == "spine.locked"
    adjustment_id = propose(double).json()["adjustment_id"]
    double.versions[OPEN_VERSION_ID].is_locked = True
    assert decide(double, adjustment_id, "accepted").status_code == 409


def test_the_spines_line_rules() -> None:
    double = FakeSpine()
    assert (
        propose(double, [{"line_no": 5, "dr": "10"}, {"line_no": 3, "cr": "9"}]).status_code == 422
    )
    assert propose(double, [{"line_no": 5, "dr": "10"}]).status_code == 422
    assert (
        propose(double, [{"line_no": 99, "dr": "10"}, {"line_no": 3, "cr": "10"}]).status_code
        == 422
    )
    assert (
        propose(
            double, [{"line_no": 5, "dr": "10", "cr": "10"}, {"line_no": 3, "cr": "10"}]
        ).status_code
        == 422
    )
    assert (
        propose(
            double, [{"line_no": 5, "ledger_name": "Rent", "dr": "10"}, {"line_no": 3, "cr": "10"}]
        ).status_code
        == 422
    )
    assert propose(double, LINES, kind="uncorrected").status_code == 422
    introduced = propose(
        double,
        [
            {
                "ledger_name": "Audit fee provision",
                "parent_chain": ["Provisions"],
                "head_id": "bs.liabilities.current.provisions",
                "cr": "25000.00",
            },
            {"line_no": 5, "dr": "25000.00"},
        ],
    )
    assert introduced.status_code == 201
    assert introduced.json()["lines"][0]["in_import"] is False
    assert introduced.json()["lines"][0]["head_id"] == "bs.liabilities.current.provisions"
    assert (
        introduced.json()["lines"][1]["head_id"] is None
    )  # the map decides an import ledger's head
    not_leaf = propose(
        double, [{"ledger_name": "X", "head_id": "bs", "cr": "1"}, {"line_no": 5, "dr": "1"}]
    )
    assert not_leaf.status_code == 422


def test_a_reclassification_posts_to_the_reclass_column_only_when_accepted() -> None:
    double = FakeSpine()
    answer = double.client().propose(
        OPEN_VERSION_ID,
        kind="reclass",
        narration="Regroup",
        working_paper_ref="E-1",
        finding_ref="M-1",
        lines=[{"line_no": 1, "dr": "700.00"}, {"line_no": 2, "cr": "700.00"}],
    )
    assert answer.kind == "reclass"
    assert double.adjusted_balance(OPEN_VERSION_ID, "Alpha Traders") == Decimal("500000.00")
    assert decide(double, str(answer.adjustment_id), "accepted").status_code == 200
    assert double.adjusted_balance(OPEN_VERSION_ID, "Alpha Traders") == Decimal("500700.00")
    assert double.adjusted_balance(OPEN_VERSION_ID, "Kotak Bank") == Decimal("119300.00")
