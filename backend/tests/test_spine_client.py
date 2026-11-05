"""The Financial Spine client (D11): error mapping, parsing, the verbs it may send."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest

from oak_misstatements.config import Settings
from oak_misstatements.errors import Conflict, Invalid, NotFound, ServiceUnavailable
from oak_misstatements.services.spine_client import SpineClient, build_spine_client, parse_version
from tests.conftest import APP_URL
from tests.fake_spine import ENGAGEMENT_ID, LOCKED_VERSION_ID, OPEN_VERSION_ID, FakeSpine


def client_answering(handler: Callable[[httpx.Request], httpx.Response]) -> SpineClient:
    return SpineClient("http://spine.test", httpx.Client(transport=httpx.MockTransport(handler)))


def test_build_returns_none_without_a_url(make_settings: Callable[..., Settings]) -> None:
    assert build_spine_client(make_settings(database_url=APP_URL)) is None
    built = build_spine_client(
        make_settings(database_url=APP_URL, spine_url="http://127.0.0.1:8000")
    )
    assert built is not None
    assert repr(built) == "SpineClient('http://127.0.0.1:8000')"


def test_the_credential_is_sent_as_a_bearer_and_never_shown() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"status": "ok"})

    spine = SpineClient(
        "http://spine.test", httpx.Client(transport=httpx.MockTransport(handler)), "s3cret"
    )
    spine.health()
    assert seen == ["Bearer s3cret"]
    assert "s3cret" not in repr(spine)


@pytest.mark.parametrize(
    ("status", "body", "error", "message"),
    [
        (
            404,
            {"detail": {"code": "x", "message": "No spine_version 1"}},
            NotFound,
            "No spine_version 1",
        ),
        (401, {"detail": "nope"}, ServiceUnavailable, "refused the configured credential"),
        (403, {"detail": "nope"}, ServiceUnavailable, "refused the configured credential"),
        (409, {"detail": {"code": "spine.locked", "message": "locked"}}, Conflict, "locked"),
        (
            422,
            {"detail": [{"loc": ["body"], "msg": "lines do not balance"}]},
            Invalid,
            "do not balance",
        ),
        (400, {"detail": "bad"}, Invalid, "bad"),
        (429, {"detail": "slow down"}, ServiceUnavailable, "answered 429"),
        (500, {"detail": "boom"}, ServiceUnavailable, "answered 500"),
    ],
)
def test_spine_answers_are_mapped_once(
    status: int, body: dict[str, object], error: type[Exception], message: str
) -> None:
    spine = client_answering(lambda _request: httpx.Response(status, json=body))
    with pytest.raises(error, match=message):
        spine.version(OPEN_VERSION_ID)


def test_transport_faults_timeouts_and_non_json_are_unavailable() -> None:
    def refuse(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    def slow(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ServiceUnavailable, match="cannot be reached"):
        client_answering(refuse).health()
    with pytest.raises(ServiceUnavailable, match="did not answer in time"):
        client_answering(slow).health()
    with pytest.raises(ServiceUnavailable, match="unexpected answer"):
        client_answering(lambda _r: httpx.Response(200, content=b"<html>")).version(OPEN_VERSION_ID)


def test_version_parsing() -> None:
    double = FakeSpine()
    version = double.client().version(LOCKED_VERSION_ID)
    assert version.engagement_id == ENGAGEMENT_ID
    assert version.is_locked
    assert version.performance_materiality == Decimal("250000.00")
    assert version.hash == "f" * 64
    with pytest.raises(ServiceUnavailable, match="unexpected answer for a version"):
        parse_version({"version_id": "not-a-uuid"})


def test_ledgers_adjustments_and_tree_come_from_the_spines_shapes() -> None:
    spine = FakeSpine().client()
    ledgers = spine.ledgers(OPEN_VERSION_ID)
    assert [ledger.line_no for ledger in ledgers] == list(range(1, 21))
    rent = ledgers[4]
    assert (rent.ledger_name, rent.head_id, rent.nature) == ("Rent", "pl.expenses.other", "PL")
    assert ledgers[6].head_id is None  # the unmapped suspense ledger
    assert spine.adjustments(OPEN_VERSION_ID) == []
    tree = spine.tree()
    assert tree.version == "double-division1-2026-11-04"
    assert tree.division == "I"
    assert tree.heads["pl.revenue.operations"].nature == "PL"
    assert tree.heads["bs"].mappable is False
    assert tree.heads["bs.liabilities.shareholders_funds"].item == "I(1)"
    assert tree.heads["bs.assets.current.cash"].side == "debit"
    assert tree.heads["pl.tax_expense"].statement == "profit_and_loss"


def test_sections_by_ancestry_and_item() -> None:
    tree = FakeSpine().client().tree()
    assert tree.section("bs.assets.current.cash") == "assets"
    assert tree.section("bs.assets.non_current.ppe.accumulated_depreciation") == "assets"
    assert tree.section("bs.liabilities.current.provisions") == "liabilities"
    assert (
        tree.section("bs.liabilities.current.other.share_application_refundable") == "liabilities"
    )
    assert tree.section("bs.liabilities.non_current.deferred_tax_liabilities") == "liabilities"
    assert tree.section("bs.liabilities.shareholders_funds.reserves.general") == "equity"
    assert tree.section("bs.liabilities.shareholders_funds.share_capital") == "equity"
    assert tree.section("bs.liabilities.share_application_money") == "unresolved"  # item I(2)
    assert tree.section("pl.expenses.other") == "pl_before_tax"
    assert tree.section("pl.revenue.operations") == "pl_before_tax"
    assert tree.section("pl.tax_expense.current") == "pl_after_tax"
    assert tree.section("pl.discontinuing_operations.profit_or_loss") == "pl_after_tax"
    assert tree.section("no.such.head") == "unresolved"
    assert tree.section(None) == "unresolved"
    # Nearest item wins: a chain walks from the head up to the first classifying item.
    assert [
        head.item
        for head in tree.chain("bs.liabilities.current.other.share_application_refundable")
    ] == [
        None,
        "I(4)(c)",
        "I(4)",
        "I",
        None,
    ]


def test_propose_sends_the_spines_body_and_reads_back_the_adjustment() -> None:
    double = FakeSpine()
    spine = double.client()
    adjustment = spine.propose(
        OPEN_VERSION_ID,
        kind="correction",
        narration="Rent not accrued",
        working_paper_ref="E-4.2",
        finding_ref="M-1",
        lines=[{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}],
    )
    assert adjustment.status == "proposed"
    assert adjustment.finding_ref == "M-1"
    assert [line.ledger_name for line in adjustment.lines] == ["Rent", "Provision for expenses"]
    assert adjustment.lines[0].dr == Decimal("10000.00")
    assert spine.adjustment(OPEN_VERSION_ID, adjustment.adjustment_id) == adjustment
    with pytest.raises(NotFound, match="no adjustment"):
        spine.adjustment(OPEN_VERSION_ID, uuid.uuid4())
    assert double.calls == [
        ("POST", f"/api/spine-versions/{OPEN_VERSION_ID}/adjustments"),
        ("GET", f"/api/spine-versions/{OPEN_VERSION_ID}/adjustments"),
        ("GET", f"/api/spine-versions/{OPEN_VERSION_ID}/adjustments"),
    ]


def test_decide_accepts_or_refuses_once_and_a_locked_version_refuses() -> None:
    from oak_misstatements.errors import Conflict

    double = FakeSpine()
    spine = double.client()
    lines = [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}]

    def proposed() -> uuid.UUID:
        return spine.propose(
            OPEN_VERSION_ID,
            kind="correction",
            narration="Rent",
            working_paper_ref="E-4.2",
            finding_ref=None,
            lines=lines,
        ).adjustment_id

    accepted = spine.decide(OPEN_VERSION_ID, proposed(), status="accepted", note="M-1 corrected")
    assert (accepted.status, accepted.decision_note) == ("accepted", "M-1 corrected")
    assert accepted.decided_by is not None and accepted.decided_at is not None
    with pytest.raises(Conflict, match="cannot be changed"):
        spine.decide(OPEN_VERSION_ID, accepted.adjustment_id, status="refused", note="again")
    refused = spine.decide(OPEN_VERSION_ID, proposed(), status="refused", note=None)
    assert (refused.status, refused.decision_note) == ("refused", None)
    with pytest.raises(NotFound):
        spine.decide(OPEN_VERSION_ID, uuid.uuid4(), status="accepted", note=None)
    open_one = proposed()
    double.versions[OPEN_VERSION_ID].is_locked = True
    with pytest.raises(Conflict, match="locked"):
        spine.decide(OPEN_VERSION_ID, open_one, status="accepted", note=None)
    assert double.calls[-1] == (
        "POST",
        f"/api/spine-versions/{OPEN_VERSION_ID}/adjustments/{open_one}/decision",
    )
