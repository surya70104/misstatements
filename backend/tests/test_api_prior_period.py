"""Prior-period uncorrected misstatements carried forward (SA 450 paragraph 11(b); spec
sections 4.1, 9 and 10.3; acceptance 5; D61): each carried item with its current-period and
its cumulative effect apart, their totals kept apart from the current year's own
misstatements and shown together with them on each basis, recorded append-only, and never
read by a gate."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from oak_misstatements.core import gates
from oak_misstatements.core import prior_period as core
from oak_misstatements.models.guard import AppendOnlyViolation
from oak_misstatements.models.prior_period import PriorPeriodItem
from tests.conftest import act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, OPEN_VERSION_ID
from tests.test_api_evaluation import evaluation, linked, raise_item, thresholds
from tests.test_api_evaluation_runs import run
from tests.test_api_transitions import move

# A prior year's rent accrual left uncorrected: the expense fell into this year instead, so
# correcting this year raises its profit; nothing of it is left in the closing figures.
REVERSED = {
    "description": "Rent for March of the prior year not accrued",
    "prior_period": "FY 2024-25",
    "source_ref": "PY schedule M-4",
    "current_profit_before_tax": "50000.00",
    "current_net_assets": "0.00",
    "cumulative_profit_before_tax": "0.00",
    "cumulative_net_assets": "0.00",
    "basis": "Accrual of the prior year reversed in April; see PY E-4.2",
}
# Depreciation understated in the prior year and never corrected: nothing new arises this
# year, and the whole of it still stands in the closing figures.
STANDING = {
    "description": "Depreciation on plant understated in the prior year",
    "prior_period": "FY 2024-25",
    "source_ref": "PY schedule M-7",
    "current_profit_before_tax": "0.00",
    "current_net_assets": "-30000.00",
    "cumulative_profit_before_tax": "-30000.00",
    "cumulative_net_assets": "-30000.00",
    "basis": "Carrying amount still overstated at the year end; see PY F-3.4",
}


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 4,00,000; PM 2,50,000; CTT 12,500
    return engagement_id


def path(engagement_id: str, rest: str = "") -> str:
    return f"/api/engagements/{engagement_id}/prior-period{rest}"


def record(api: TestClient, engagement_id: str, body: dict[str, Any] | None = None) -> Any:
    return api.post(path(engagement_id), json=REVERSED if body is None else body)


def listing(api: TestClient, engagement_id: str) -> Any:
    answer = api.get(path(engagement_id))
    assert answer.status_code == 200, answer.text
    return answer.json()


def pairs(gross_pbt: str, net_pbt: str, gross_na: str, net_na: str) -> dict[str, Any]:
    return {
        "profit_before_tax": {"gross": gross_pbt, "net": net_pbt},
        "net_assets": {"gross": gross_na, "net": net_na},
    }


NIL = pairs("0.00", "0.00", "0.00", "0.00")


# ---- nothing carried --------------------------------------------------------------------------


def test_with_nothing_carried_the_two_views_are_the_current_years_aggregate(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")
    block = evaluation(api, engagement_id)["prior_period"]
    assert block["items"] == []
    assert block["totals"] == {"current_period": NIL, "cumulative": NIL}
    year = pairs("60000.00", "-60000.00", "60000.00", "-60000.00")
    assert block["current_year"] == year
    assert block["with_prior_period"] == {"current_period": year, "cumulative": year}
    assert block["read_by_gates"] is False
    assert block["reaches"] == {
        "current_period": {"pm": [], "om": []},
        "cumulative": {"pm": [], "om": []},
    }
    assert "11(b)" in block["basis"]
    answer = listing(api, engagement_id)
    assert (answer["items"], answer["removed"], answer["history"]) == ([], [], [])
    assert answer["authorisation"]["enforced"] is False


# ---- acceptance 5 -----------------------------------------------------------------------------


def test_acceptance_5_prior_period_items_show_current_period_and_cumulative_effects_apart(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")  # M-1
    raise_item(api, engagement_id, "40000.00")  # M-2
    before = evaluation(api, engagement_id)

    act_as(api, "manager@firm")
    first = record(api, engagement_id, REVERSED)
    assert first.status_code == 201, first.text
    assert first.json()["recorded"]["ref"] == "PY-1"
    second = record(api, engagement_id, STANDING)
    assert second.status_code == 201, second.text
    assert second.json()["recorded"]["ref"] == "PY-2"

    after = evaluation(api, engagement_id)
    block = after["prior_period"]
    # Each item appears, with its two effects apart, on profit and on net assets.
    assert [
        (item["ref"], item["prior_period"], item["current_period"], item["cumulative"])
        for item in block["items"]
    ] == [
        (
            "PY-1",
            "FY 2024-25",
            {"profit_before_tax": "50000.00", "net_assets": "0.00"},
            {"profit_before_tax": "0.00", "net_assets": "0.00"},
        ),
        (
            "PY-2",
            "FY 2024-25",
            {"profit_before_tax": "0.00", "net_assets": "-30000.00"},
            {"profit_before_tax": "-30000.00", "net_assets": "-30000.00"},
        ),
    ]
    assert block["items"][0]["basis"] == REVERSED["basis"]
    assert block["items"][0]["recorded_by"] == "manager@firm"
    assert block["items"][0]["rolled_forward"] is False and block["items"][0]["prior"] is None
    # Their totals, each basis apart: gross with no netting between items, net signed.
    assert block["totals"] == {
        "current_period": pairs("50000.00", "50000.00", "30000.00", "-30000.00"),
        "cumulative": pairs("30000.00", "-30000.00", "30000.00", "-30000.00"),
    }
    # The current year's own misstatements, distinct from both.
    assert block["current_year"] == pairs("100000.00", "-100000.00", "100000.00", "-100000.00")
    # And the two together, both ways: no one method is chosen.
    assert block["with_prior_period"] == {
        "current_period": pairs("150000.00", "-50000.00", "130000.00", "-130000.00"),
        "cumulative": pairs("130000.00", "-130000.00", "130000.00", "-130000.00"),
    }
    assert block["complete"] is True
    # The current year's aggregate, its gates and the sign-off decision are exactly as before.
    for key in ("aggregate", "gates", "tests", "sign_off", "items", "individually_significant"):
        assert after[key] == before[key], key
    # The schedule of prior-period items says the same.
    answer = listing(api, engagement_id)
    assert [item["ref"] for item in answer["items"]] == ["PY-1", "PY-2"]
    assert answer["items"] == block["items"]
    assert answer["totals"] == block["totals"]
    assert [(entry["ref"], entry["version_no"]) for entry in answer["history"]] == [
        ("PY-1", 1),
        ("PY-2", 1),
    ]


def test_gross_does_not_net_one_carried_item_against_another(api: TestClient) -> None:
    engagement_id = ready(api)
    assert record(api, engagement_id, REVERSED).status_code == 201  # +50,000 this period
    opposite = {
        **REVERSED,
        "description": "Prior-year sales cut-off: sales of April taken in March",
        "current_profit_before_tax": "-50000.00",
        "basis": "Reversed in April; see PY R-5.3",
    }
    assert record(api, engagement_id, opposite).status_code == 201
    totals = evaluation(api, engagement_id)["prior_period"]["totals"]["current_period"]
    assert totals["profit_before_tax"] == {"gross": "100000.00", "net": "0.00"}


# ---- no gate reads the carried items ------------------------------------------------------------


def test_the_gates_test_the_current_year_and_the_carried_items_are_shown_beside_them(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "200000.00")  # below PM 2,50,000 on its own
    large = {
        **STANDING,
        "current_net_assets": "-60000.00",
        "cumulative_profit_before_tax": "-60000.00",
        "cumulative_net_assets": "-60000.00",
    }
    assert record(api, engagement_id, large).status_code == 201
    answer = evaluation(api, engagement_id)
    block = answer["prior_period"]
    assert block["with_prior_period"]["cumulative"]["profit_before_tax"]["gross"] == "260000.00"
    # With the carried item the cumulative view reaches PM on every measure, and the
    # current-period view reaches it on net assets only. That is said, as information.
    assert block["reaches"] == {
        "current_period": {"pm": ["net_assets.gross", "net_assets.net"], "om": []},
        "cumulative": {
            "pm": ["profit.gross", "profit.net", "net_assets.gross", "net_assets.net"],
            "om": [],
        },
    }
    # No gate reads it: the soft gate tests the current year's 2,00,000 and stays clear.
    assert block["read_by_gates"] is False
    assert answer["gates"]["soft"]["status"] == "clear"
    assert answer["gates"]["hard"]["status"] == "clear"
    assert answer["sign_off"]["blocked"] is False
    assert answer["aggregate"]["profit_before_tax"]["gross"] == "200000.00"
    # A module reading the gate sees the carried figures beside the status.
    for gate in ("opinion", "sign-off"):
        exposure = api.get(f"/api/engagements/{engagement_id}/gates/{gate}").json()
        assert exposure["status"] == "open", gate
        assert exposure["figures"]["profit_before_tax"]["gross"] == "200000.00"
        assert exposure["prior_period"]["items"] == [{"ref": "PY-1", "version_no": 1}]
        assert exposure["prior_period"]["reaches"] == block["reaches"]
        assert exposure["prior_period"]["read_by_gates"] is False


def test_without_thresholds_the_carried_items_are_still_shown_and_reach_nothing(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    assert record(api, engagement_id, STANDING).status_code == 201
    block = evaluation(api, engagement_id)["prior_period"]
    assert [item["ref"] for item in block["items"]] == ["PY-1"]
    assert block["reaches"] is None
    assert block["totals"]["cumulative"]["net_assets"] == {"gross": "30000.00", "net": "-30000.00"}


# ---- revising and removing: new versions, nothing changed ----------------------------------------


def test_revising_an_item_adds_a_version_and_keeps_the_first(api: TestClient) -> None:
    engagement_id = ready(api)
    assert record(api, engagement_id, STANDING).status_code == 201
    act_as(api, "manager@firm")
    revised = {
        "current_profit_before_tax": "0.00",
        "current_net_assets": "-25000.00",
        "cumulative_profit_before_tax": "-25000.00",
        "cumulative_net_assets": "-25000.00",
        "basis": "Useful life re-read: the understatement was 25,000; see PY F-3.4 revised",
    }
    answer = api.post(path(engagement_id, "/PY-1/revisions"), json=revised)
    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert (body["recorded"]["ref"], body["recorded"]["version_no"]) == ("PY-1", 2)
    assert body["recorded"]["recorded_by"] == "manager@firm"
    assert [item["version_no"] for item in body["items"]] == [2]
    assert body["items"][0]["cumulative"] == {
        "profit_before_tax": "-25000.00",
        "net_assets": "-25000.00",
    }
    # What it is, and where it came from, do not change with its figures.
    assert body["items"][0]["description"] == STANDING["description"]
    assert body["items"][0]["source_ref"] == STANDING["source_ref"]
    # Both versions are kept, the first as it was recorded.
    assert [
        (e["version_no"], e["cumulative"]["net_assets"], e["recorded_by"]) for e in body["history"]
    ] == [(1, "-30000.00", "senior@firm"), (2, "-25000.00", "manager@firm")]
    assert body["totals"]["cumulative"]["net_assets"] == {"gross": "25000.00", "net": "-25000.00"}
    # The same figures on the same basis are nothing to record.
    again = api.post(path(engagement_id, "/PY-1/revisions"), json=revised)
    assert again.status_code == 409 and "nothing was saved" in again.json()["detail"]
    assert len(listing(api, engagement_id)["history"]) == 2


def test_removing_an_item_needs_a_reason_and_keeps_its_history(api: TestClient) -> None:
    engagement_id = ready(api)
    assert record(api, engagement_id, REVERSED).status_code == 201
    assert record(api, engagement_id, STANDING).status_code == 201
    for blank in ({}, {"reason": ""}, {"reason": "   "}):
        refused = api.post(path(engagement_id, "/PY-1/removal"), json=blank)
        assert refused.status_code == 422, blank
    assert len(listing(api, engagement_id)["items"]) == 2

    removed = api.post(
        path(engagement_id, "/PY-1/removal"),
        json={"reason": "Corrected by management in this year's books; see E-9"},
    )
    assert removed.status_code == 201, removed.text
    body = removed.json()
    assert [item["ref"] for item in body["items"]] == ["PY-2"]
    assert [(item["ref"], item["version_no"], item["carried"]) for item in body["removed"]] == [
        ("PY-1", 2, False)
    ]
    # The removing version keeps the item's figures and holds the reason.
    assert body["removed"][0]["current_period"]["profit_before_tax"] == "50000.00"
    assert body["removed"][0]["basis"] == "Corrected by management in this year's books; see E-9"
    assert [(e["ref"], e["version_no"], e["carried"]) for e in body["history"]] == [
        ("PY-1", 1, True),
        ("PY-1", 2, False),
        ("PY-2", 1, True),
    ]
    # It is out of the totals and out of the evaluation.
    block = evaluation(api, engagement_id)["prior_period"]
    assert [item["ref"] for item in block["items"]] == ["PY-2"]
    assert block["totals"]["current_period"]["profit_before_tax"] == {
        "gross": "0.00",
        "net": "0.00",
    }
    # A removed item cannot be removed or revised again; a new item takes the next reference.
    again = api.post(path(engagement_id, "/PY-1/removal"), json={"reason": "twice"})
    assert again.status_code == 409 and "no longer carried" in again.json()["detail"]
    revision = {key: STANDING[key] for key in STANDING if key.startswith(("current", "cumul"))}
    revision["basis"] = "x"
    assert api.post(path(engagement_id, "/PY-1/revisions"), json=revision).status_code == 409
    assert record(api, engagement_id, REVERSED).json()["recorded"]["ref"] == "PY-3"


# ---- what is refused --------------------------------------------------------------------------


def test_the_effects_and_their_basis_are_mandatory_and_nothing_else_is_taken(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    for change in (
        {"basis": ""},
        {"basis": "   "},
        {"basis": None},
        {"current_profit_before_tax": None},
        {"cumulative_net_assets": None},
        {"cumulative_profit_before_tax": "100.005"},  # three decimal places
        {"description": None},  # entered by hand: it must say what it is
        {"source_ref": None},  # and where it comes from
        {"prior_period": "  "},
        {"recorded_by": "partner@firm"},  # who acts is never taken from the request
        {"at": "2020-01-01T00:00:00Z"},
        {"carried": False},
        {"prior": {"profit_before_tax": "1.00", "net_assets": "1.00"}},
    ):
        body = {key: value for key, value in {**REVERSED, **change}.items() if value is not None}
        refused = record(api, engagement_id, body)
        assert refused.status_code == 422, change
    assert listing(api, engagement_id)["history"] == []
    # An engagement or an item that does not exist.
    missing = str(uuid.uuid4())
    assert api.get(path(missing)).status_code == 404
    assert record(api, missing).status_code == 404
    assert api.post(path(engagement_id, "/PY-9/removal"), json={"reason": "x"}).status_code == 404
    # An identity is required, as for every write.
    act_as(api, None)
    assert record(api, engagement_id).status_code == 503
    act_as(api, "senior@firm")
    assert listing(api, engagement_id)["history"] == []


def test_the_versions_cannot_be_changed_or_deleted(api: TestClient) -> None:
    engagement_id = ready(api)
    assert record(api, engagement_id, STANDING).status_code == 201
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        row = session.scalars(select(PriorPeriodItem)).one()
        row.cumulative_net_assets = Decimal("0.00")
        with pytest.raises(AppendOnlyViolation, match="never an update"):
            session.flush()
    with factory() as session:
        row = session.scalars(select(PriorPeriodItem)).one()
        session.delete(row)
        with pytest.raises(AppendOnlyViolation, match="never deleted"):
            session.flush()
    with factory() as session:
        with pytest.raises(AppendOnlyViolation, match="UPDATE is not allowed"):
            session.execute(update(PriorPeriodItem).values(carried=False))
        with pytest.raises(AppendOnlyViolation, match="DELETE is not allowed"):
            session.execute(delete(PriorPeriodItem))
    assert listing(api, engagement_id)["items"][0]["cumulative"]["net_assets"] == "-30000.00"


# ---- rolling forward from another engagement ----------------------------------------------------


def prior_engagement(api: TestClient) -> tuple[str, Any, Any]:
    """Another engagement, with one item left uncorrected and one corrected."""
    created = api.post(
        "/api/engagements",
        json={
            "label": "FY25",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    )
    assert created.status_code == 201, created.text
    other = str(created.json()["id"])
    thresholds(api, other)
    left = raise_item(api, other, "60000.00")  # M-1: communicated, never corrected
    assert move(api, left["id"], "communicated").status_code == 201
    settled = raise_item(api, other, "45000.00")  # M-2: corrected
    assert move(api, settled["id"], "communicated").status_code == 201
    assert move(api, settled["id"], "corrected").status_code == 201
    return other, left, settled


def test_a_misstatement_left_uncorrected_elsewhere_is_rolled_forward_with_its_effects_there(
    api: TestClient,
) -> None:
    use_spine(api)
    other, left, settled = prior_engagement(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)

    offered = api.get(path(engagement_id, "/candidates"), params={"from_engagement_id": other})
    assert offered.status_code == 200, offered.text
    body = offered.json()
    assert body["from_engagement"] == {"id": other, "label": "FY25"}
    # Only what is uncorrected there is offered, with its effects there.
    assert [
        (c["ref"], c["state"], c["profit_before_tax"], c["net_assets"], c["carried_as"])
        for c in body["candidates"]
    ] == [("M-1", "communicated", "-60000.00", "-60000.00", None)]
    assert body["candidates"][0]["misstatement_id"] == left["id"]

    rolled = record(
        api,
        engagement_id,
        {
            "prior_period": "FY 2024-25",
            "source_misstatement_id": left["id"],
            "current_profit_before_tax": "60000.00",
            "current_net_assets": "0.00",
            "cumulative_profit_before_tax": "0.00",
            "cumulative_net_assets": "0.00",
            "basis": "Accrual reversed in April of this year",
        },
    )
    assert rolled.status_code == 201, rolled.text
    item = rolled.json()["recorded"]
    assert item["ref"] == "PY-1" and item["rolled_forward"] is True
    assert item["source_misstatement_id"] == left["id"]
    # Copied by the backend from its own record of the other engagement, never sent.
    assert item["prior"] == {"profit_before_tax": "-60000.00", "net_assets": "-60000.00"}
    assert item["description"] == "factual item of 60000.00"
    assert item["source_ref"] == "FY25, M-1"
    # Its effects here are the person's, as entered.
    assert item["current_period"] == {"profit_before_tax": "60000.00", "net_assets": "0.00"}

    # It is now shown as carried, and cannot be rolled forward twice.
    again = api.get(path(engagement_id, "/candidates"), params={"from_engagement_id": other})
    assert again.json()["candidates"][0]["carried_as"] == "PY-1"
    twice = record(
        api,
        engagement_id,
        {**REVERSED, "source_misstatement_id": left["id"]},
    )
    assert twice.status_code == 409 and "already carried forward" in twice.json()["detail"]
    # A corrected misstatement is not carried forward.
    corrected = record(api, engagement_id, {**REVERSED, "source_misstatement_id": settled["id"]})
    assert corrected.status_code == 409 and "corrected there" in corrected.json()["detail"]
    assert len(listing(api, engagement_id)["history"]) == 1
    # Nothing was written to the other engagement.
    assert listing(api, other)["history"] == []


def test_what_cannot_be_rolled_forward_is_refused(api: TestClient) -> None:
    engagement_id = ready(api)
    own = raise_item(api, engagement_id, "60000.00")
    # A misstatement of this engagement is the current year's.
    mine = record(api, engagement_id, {**REVERSED, "source_misstatement_id": own["id"]})
    assert mine.status_code == 422 and "current year's" in mine.json()["detail"]
    same = api.get(path(engagement_id, "/candidates"), params={"from_engagement_id": engagement_id})
    assert same.status_code == 422
    # A misstatement or an engagement that does not exist.
    unknown = record(api, engagement_id, {**REVERSED, "source_misstatement_id": str(uuid.uuid4())})
    assert unknown.status_code == 404
    nowhere = api.get(
        path(engagement_id, "/candidates"), params={"from_engagement_id": str(uuid.uuid4())}
    )
    assert nowhere.status_code == 404
    assert listing(api, engagement_id)["history"] == []


# ---- evaluation runs: py_carried ----------------------------------------------------------------


def test_a_run_records_what_it_saw_of_the_carried_items_and_goes_stale_when_they_change(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")
    first = run(api, engagement_id).json()
    # A run made with nothing carried says so.
    assert first["py_carried"]["items"] == []
    assert first["py_carried"]["totals"] == {"current_period": NIL, "cumulative": NIL}
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "current"

    assert record(api, engagement_id, STANDING).status_code == 201
    stale = evaluation(api, engagement_id)["latest_run"]
    assert stale["status"] == "stale"
    assert "a prior-period item has been recorded, revised or removed" in stale["detail"]

    second = run(api, engagement_id).json()
    carried = second["py_carried"]
    # Labels and aggregates: which version of which item, never one item's figures.
    assert carried["items"] == [{"ref": "PY-1", "version_no": 1}]
    assert carried["totals"]["cumulative"] == pairs(
        "30000.00", "-30000.00", "30000.00", "-30000.00"
    )
    assert carried["current_year"] == pairs("60000.00", "-60000.00", "60000.00", "-60000.00")
    assert carried["with_prior_period"]["cumulative"] == pairs(
        "90000.00", "-90000.00", "90000.00", "-90000.00"
    )
    assert carried["with_prior_period"]["current_period"] == pairs(
        "60000.00", "-60000.00", "90000.00", "-90000.00"
    )
    assert carried["read_by_gates"] is False
    # The four aggregate columns remain the current year's.
    assert (second["agg_gross_pbt"], second["agg_net_na"]) == ("60000.00", "-60000.00")
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "current"

    # A revision and a removal each make it stale again; each run stays as it was recorded.
    revision = {key: STANDING[key] for key in STANDING if key.startswith(("current", "cumul"))}
    revision.update(cumulative_net_assets="-20000.00", basis="Re-read; see PY F-3.4")
    assert api.post(path(engagement_id, "/PY-1/revisions"), json=revision).status_code == 201
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "stale"
    third = run(api, engagement_id).json()
    assert third["py_carried"]["items"] == [{"ref": "PY-1", "version_no": 2}]
    assert api.post(path(engagement_id, "/PY-1/removal"), json={"reason": "x"}).status_code == 201
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "stale"
    old = api.get(f"/api/evaluation-runs/{second['id']}").json()
    assert old["py_carried"] == carried


# ---- the sums themselves ------------------------------------------------------------------------


def test_the_totals_sum_gross_without_netting_and_net_signed() -> None:
    def carried(ref: str, *values: str) -> core.Carried:
        return core.Carried(ref, 1, *(Decimal(value) for value in values))

    items = [
        carried("PY-1", "50000.00", "0.00", "0.00", "0.00"),
        carried("PY-2", "-20000.00", "-30000.00", "-30000.00", "-30000.00"),
    ]
    current = core.total(items, "current_period")
    assert current.profit == core.Pair(Decimal("70000.00"), Decimal("30000.00"))
    assert current.net_assets == core.Pair(Decimal("30000.00"), Decimal("-30000.00"))
    cumulative = core.total(items, "cumulative")
    assert cumulative.profit == core.Pair(Decimal("30000.00"), Decimal("-30000.00"))
    assert core.total([], "cumulative") == core.Effect(
        core.Pair(core.ZERO, core.ZERO), core.Pair(core.ZERO, core.ZERO)
    )
    # Together with the current year's aggregate: gross adds to gross, net to net.
    year = core.current_year(gates.aggregate([]))
    assert year.plus(current) == current
    # A measure is reached at the line itself, and a net figure by its size.
    assert core.reached(cumulative, Decimal("30000.00")) == core.MEASURES
    assert core.reached(cumulative, Decimal("30000.01")) == ()
    assert core.reached(current, Decimal("40000.00")) == ("profit.gross",)
