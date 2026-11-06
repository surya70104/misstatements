"""The TCWG extract (SA 450 paragraph 12; spec section 2 row 12, section 6 item 2;
acceptance 9; D62): every uncorrected misstatement, the material ones named individually,
the others summarised and listed, the totals, the effect on the opinion and the request to
correct. Read-only, and computed from the evaluation as it stands."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from oak_misstatements.core import gates, tcwg
from oak_misstatements.core.banding import Band
from tests.conftest import use_spine
from tests.fake_spine import FakeSpine
from tests.test_api_evaluation import evaluation, linked, raise_item, thresholds
from tests.test_api_evaluation_runs import run
from tests.test_api_transitions import move


def ready(api: TestClient) -> tuple[str, FakeSpine]:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 4,00,000; PM 2,50,000; CTT 12,500
    return engagement_id, spine


def extract(api: TestClient, engagement_id: str) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/tcwg-extract")
    assert answer.status_code == 200, answer.text
    return answer.json()


def escalate(api: TestClient, misstatement_id: str, factor: str, note: str) -> None:
    answer = api.post(
        f"/api/misstatements/{misstatement_id}/qualitative", json={"factor": factor, "note": note}
    )
    assert answer.status_code == 201, answer.text


def refs(rows: list[dict[str, Any]]) -> list[str]:
    return [row["ref"] for row in rows]


def both(gross_pbt: str, net_pbt: str, gross_na: str, net_na: str) -> dict[str, Any]:
    return {
        "profit_before_tax": {"gross": gross_pbt, "net": net_pbt},
        "net_assets": {"gross": gross_na, "net": net_na},
    }


def full_schedule(api: TestClient, engagement_id: str) -> dict[str, Any]:
    """Nine misstatements: every place an item can fall, and every state."""
    items = {
        "above_pm": raise_item(api, engagement_id, "300000.00"),  # M-1
        "above_om": raise_item(api, engagement_id, "420000.00", type="judgemental"),  # M-2
        "escalated": raise_item(api, engagement_id, "3000.00"),  # M-3: below CTT
        "ordinary": raise_item(api, engagement_id, "60000.00"),  # M-4
        "projected": raise_item(api, engagement_id, "40000.00", type="projected"),  # M-5
        "trivial": raise_item(api, engagement_id, "2000.00"),  # M-6: below CTT
        "corrected": raise_item(api, engagement_id, "45000.00"),  # M-7
        "withdrawn": raise_item(api, engagement_id, "20000.00"),  # M-8
        "refused": raise_item(api, engagement_id, "50000.00"),  # M-9
    }
    escalate(api, items["escalated"]["id"], "fraud", "Suspected override of controls; see E-12")
    for key in ("corrected", "withdrawn", "refused"):
        assert move(api, items[key]["id"], "communicated").status_code == 201
    assert move(api, items["corrected"]["id"], "corrected").status_code == 201
    assert move(api, items["withdrawn"]["id"], "withdrawn", "Raised in error").status_code == 201
    assert (
        move(
            api, items["refused"]["id"], "refused", "Management considers it immaterial"
        ).status_code
        == 201
    )
    return items


# ---- acceptance 9 -----------------------------------------------------------------------------


def test_acceptance_9_the_extract_names_every_individually_material_item(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    full_schedule(api, engagement_id)
    answer = extract(api, engagement_id)

    # Named individually: above PM, at or above OM, and escalated whatever its amount.
    named = answer["named_individually"]
    assert refs(named) == ["M-1", "M-2", "M-3"]
    assert [[reason["code"] for reason in item["reasons"]] for item in named] == [
        ["above_pm"],
        ["above_pm", "at_or_above_om"],
        ["escalated"],
    ]
    assert "performance materiality" in named[0]["reasons"][0]["text"]
    assert (named[0]["band"], named[2]["band"]) == ("individually_significant", "clearly_trivial")
    assert (named[0]["profit_before_tax"], named[0]["net_assets"]) == ("-300000.00", "-300000.00")
    # Every item the evaluation's individual test finds is among them (SA 450 paragraph 11).
    individual = evaluation(api, engagement_id)["tests"]["individual"]
    assert set(individual["individually_significant"]) <= set(refs(named))
    assert set(individual["at_or_above_om"]) <= set(refs(named))
    assert {entry["ref"] for entry in individual["escalated"]} <= set(refs(named))
    assert "acceptance 9" in answer["basis"] and "B14" in answer["basis"]

    # The remaining accumulated items: summarised by type, and listed.
    other = answer["other_uncorrected"]
    assert refs(other["items"]) == ["M-4", "M-5", "M-9"]
    assert [(group["type"], group["count"]) for group in other["groups"]] == [
        ("factual", 2),
        ("judgemental", 0),
        ("projected", 1),
    ]
    assert other["groups"][0]["profit_before_tax"] == {"gross": "110000.00", "net": "-110000.00"}
    assert other["groups"][2]["net_assets"] == {"gross": "40000.00", "net": "-40000.00"}
    # A refused item is still uncorrected, and carries management's reason.
    assert other["items"][2]["state"] == "refused"
    assert other["items"][2]["refusal_reason"] == "Management considers it immaterial"

    # Outside the communication: clearly trivial and not accumulated; corrected; withdrawn.
    outside = answer["not_communicated"]
    assert refs(outside["clearly_trivial"]["items"]) == ["M-6"]
    assert outside["clearly_trivial"]["total"]["profit_before_tax_gross"] == "2000.00"
    assert outside["not_uncorrected"] == [
        {"ref": "M-7", "state": "corrected"},
        {"ref": "M-8", "state": "withdrawn"},
    ]
    assert answer["undetermined"] == []
    assert answer["counts"] == {
        "communicated": 6,
        "named_individually": 3,
        "undetermined": 0,
        "other_uncorrected": 3,
        "clearly_trivial_not_accumulated": 1,
    }
    assert (answer["status"], answer["incomplete_because"]) == ("ready", [])
    assert answer["engagement"] == {"id": engagement_id, "label": "FY26"}
    assert answer["threshold"]["pm"] == "250000.00"
    assert answer["read_only"] is True


def test_every_uncorrected_item_is_placed_once_and_the_totals_tie_to_the_aggregate(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    full_schedule(api, engagement_id)
    answer = extract(api, engagement_id)
    placed = (
        refs(answer["named_individually"])
        + refs(answer["undetermined"])
        + refs(answer["other_uncorrected"]["items"])
        + refs(answer["not_communicated"]["clearly_trivial"]["items"])
    )
    live = evaluation(api, engagement_id)
    uncorrected = [item["ref"] for item in live["items"] if item["uncorrected"]]
    assert sorted(placed) == sorted(uncorrected) and len(set(placed)) == len(placed)

    totals = answer["totals"]
    assert totals["named_individually"] == {
        "count": 3,
        **both("723000.00", "-723000.00", "723000.00", "-723000.00"),
    }
    assert totals["other_uncorrected"] == {
        "count": 3,
        **both("150000.00", "-150000.00", "150000.00", "-150000.00"),
    }
    # The two together are the evaluation's own aggregate, to the paisa, on every measure.
    whole = totals["all_uncorrected"]
    assert whole["complete"] is True
    assert whole["count"] == len(live["aggregate"]["counted"]) == 6
    for measure in ("profit_before_tax", "net_assets"):
        assert whole[measure] == live["aggregate"][measure]
        for way in ("gross", "net"):
            together = Decimal(totals["named_individually"][measure][way]) + Decimal(
                totals["other_uncorrected"][measure][way]
            )
            assert together == Decimal(whole[measure][way]), (measure, way)
    assert whole["profit_before_tax"]["gross"] == "873000.00"
    # The groups add up to the others.
    groups = answer["other_uncorrected"]["groups"]
    assert sum(group["count"] for group in groups) == 3
    assert sum(Decimal(group["profit_before_tax"]["gross"]) for group in groups) == Decimal(
        "150000"
    )


def test_a_named_item_says_what_its_type_must_say_and_shows_its_lines(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    items = full_schedule(api, engagement_id)
    named = {item["ref"]: item for item in extract(api, engagement_id)["named_individually"]}
    factual, judgemental, escalated = named["M-1"], named["M-2"], named["M-3"]
    assert factual["id"] == items["above_pm"]["id"]
    assert (factual["type"], factual["state"]) == ("factual", "raised")
    assert factual["description"] == "factual item of 300000.00"
    assert factual["source_ref"] == "E-1"
    # Its Dr/Cr lines, as the Financial Spine holds them.
    assert [(line["ledger_name"], line["dr"], line["cr"]) for line in factual["lines"]] == [
        ("Rent", "300000.00", "0.00"),
        ("Provision for expenses", "0.00", "300000.00"),
    ]
    assert (factual["range"], factual["factors"]) == (None, [])
    # A judgemental item carries its range (spec section 3.2).
    assert judgemental["range"] == {"low": "420000.00", "high": "420000.00"}
    # An escalated item carries the factor and the recorded reason (spec section 5).
    assert [(f["factor"], f["note"]) for f in escalated["factors"]] == [
        ("fraud", "Suspected override of controls; see E-12")
    ]
    assert "fraud" in escalated["factors"][0]["text"]


def test_a_projected_item_above_pm_names_its_sample_and_a_refused_one_its_reason(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    projected = raise_item(api, engagement_id, "260000.00", type="projected")
    assert move(api, projected["id"], "communicated").status_code == 201
    assert (
        move(api, projected["id"], "refused", "Management disputes the sample").status_code == 201
    )
    [named] = extract(api, engagement_id)["named_individually"]
    assert (named["ref"], named["type"], named["state"]) == ("M-1", "projected", "refused")
    assert named["sample_ref"] == "S-1"
    assert named["projection_basis"] == "ratio of error in the sample"
    # Refusing it releases the block on sign-off; it does not make it less significant.
    assert named["refusal_reason"] == "Management disputes the sample"
    assert [reason["code"] for reason in named["reasons"]] == ["above_pm"]


def test_an_item_exactly_at_pm_is_not_above_it_and_is_not_named(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "250000.00")  # at PM: accumulated, not individually significant
    raise_item(api, engagement_id, "250000.01")  # above it
    answer = extract(api, engagement_id)
    assert refs(answer["named_individually"]) == ["M-2"]
    assert refs(answer["other_uncorrected"]["items"]) == ["M-1"]


def test_an_item_stops_being_named_when_it_is_corrected_or_its_factor_is_cleared(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    large = raise_item(api, engagement_id, "300000.00")
    small = raise_item(api, engagement_id, "20000.00")
    escalate(api, small["id"], "related_party", "Sale to a director's firm")
    assert refs(extract(api, engagement_id)["named_individually"]) == ["M-1", "M-2"]

    assert move(api, large["id"], "communicated").status_code == 201
    assert move(api, large["id"], "corrected").status_code == 201
    cleared = api.post(
        f"/api/misstatements/{small['id']}/qualitative/related_party/clear",
        json={"note": "Not a related party after all"},
    )
    assert cleared.status_code == 201, cleared.text
    answer = extract(api, engagement_id)
    assert answer["named_individually"] == []
    assert refs(answer["other_uncorrected"]["items"]) == ["M-2"]
    assert answer["not_communicated"]["not_uncorrected"] == [{"ref": "M-1", "state": "corrected"}]


def test_clearly_trivial_items_accumulated_together_are_communicated(api: TestClient) -> None:
    """D57: items clearly trivial one by one that together reach the threshold are all
    accumulated. They are then part of the communication, not left outside it."""
    engagement_id, _spine = ready(api)
    for _ in range(3):
        raise_item(api, engagement_id, "5000.00")  # 15,000 together, CTT 12,500
    answer = extract(api, engagement_id)
    assert refs(answer["other_uncorrected"]["items"]) == ["M-1", "M-2", "M-3"]
    assert answer["not_communicated"]["clearly_trivial"]["items"] == []
    assert answer["not_communicated"]["clearly_trivial"]["total"]["accumulated_together"] == [
        "M-1",
        "M-2",
        "M-3",
    ]
    assert answer["totals"]["all_uncorrected"]["profit_before_tax"]["gross"] == "15000.00"


# ---- the effect on the opinion ----------------------------------------------------------------


def test_the_opinion_effect_is_the_opinion_gates_reading(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    raise_item(api, engagement_id, "40000.00", type="projected")
    intact = extract(api, engagement_id)
    effect = intact["opinion_effect"]
    assert effect["unmodified_opinion"] == "not_blocked"
    assert effect["statement"] == (
        "The size of the uncorrected misstatements does not block an unmodified opinion."
    )
    assert (effect["blocked_by"], effect["undetermined_because"]) == ([], [])
    assert effect["hard_gate"]["status"] == "clear"
    assert effect["conclusion"] == {"status": "none", "determination": None, "run_no": None}
    assert intact["named_individually"] == []
    gate = api.get(f"/api/engagements/{engagement_id}/gates/opinion").json()
    assert gate["status"] == "open"

    # The aggregate reaches overall materiality: an unmodified opinion is blocked.
    raise_item(api, engagement_id, "300000.00")
    blocked = extract(api, engagement_id)["opinion_effect"]
    assert blocked["unmodified_opinion"] == "blocked"
    assert blocked["statement"] == (
        "An unmodified opinion cannot be issued on the uncorrected misstatements as they stand."
    )
    assert blocked["hard_gate"]["status"] == "fires"
    assert blocked["hard_gate"]["line"] == "400000.00"
    assert blocked["hard_gate"]["highest_measure"] == "400000.00"
    gate = api.get(f"/api/engagements/{engagement_id}/gates/opinion").json()
    assert gate["status"] == "blocked"
    assert blocked["blocked_by"] == gate["blocked_by"]
    assert "overall materiality" in blocked["blocked_by"][0]
    assert "unmodified opinion is blocked" in blocked["scope"]


def test_the_extract_carries_the_prior_period_items_and_says_no_gate_reads_them(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    recorded = api.post(
        f"/api/engagements/{engagement_id}/prior-period",
        json={
            "description": "Depreciation understated in the prior year",
            "prior_period": "FY 2024-25",
            "source_ref": "PY schedule M-7",
            "current_profit_before_tax": "0.00",
            "current_net_assets": "-30000.00",
            "cumulative_profit_before_tax": "-30000.00",
            "cumulative_net_assets": "-30000.00",
            "basis": "Still stands at the year end",
        },
    )
    assert recorded.status_code == 201, recorded.text
    answer = extract(api, engagement_id)
    block = answer["prior_period"]
    assert refs(block["items"]) == ["PY-1"]
    assert block["items"][0]["cumulative"] == {
        "profit_before_tax": "-30000.00",
        "net_assets": "-30000.00",
    }
    assert block["with_prior_period"]["cumulative"]["net_assets"]["gross"] == "90000.00"
    assert block == evaluation(api, engagement_id)["prior_period"]
    assert answer["opinion_effect"]["reads_prior_period"] is False
    # The current year's totals are not changed by it.
    assert answer["totals"]["all_uncorrected"]["net_assets"]["gross"] == "60000.00"


# ---- the request ------------------------------------------------------------------------------


def test_the_request_to_correct_is_made_when_something_uncorrected_is_accumulated(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    nothing = extract(api, engagement_id)
    assert nothing["request"]["applies"] is False
    assert "nothing to request" in nothing["request"]["text"]
    assert nothing["counts"]["communicated"] == 0
    assert (nothing["status"], nothing["opinion_effect"]["unmodified_opinion"]) == (
        "ready",
        "not_blocked",
    )
    # Only a clearly trivial item, which is not accumulated: still nothing to request.
    trivial = raise_item(api, engagement_id, "2000.00")
    assert extract(api, engagement_id)["request"]["applies"] is False

    raise_item(api, engagement_id, "60000.00")
    request = extract(api, engagement_id)["request"]
    assert request["applies"] is True
    assert request["text"] == (
        "We request that the uncorrected misstatements set out in this schedule be corrected."
    )
    assert "SA 450 paragraph 12" in request["basis"]
    # Once everything accumulated is corrected, there is again nothing to request.
    assert trivial["ref"] == "M-1"
    second = evaluation(api, engagement_id)["items"][1]["id"]
    assert move(api, second, "communicated").status_code == 201
    assert move(api, second, "corrected").status_code == 201
    assert extract(api, engagement_id)["request"]["applies"] is False


# ---- an extract that cannot be relied on says so -----------------------------------------------


def test_without_thresholds_every_item_is_undetermined_and_the_extract_is_incomplete(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    raise_item(api, engagement_id, "300000.00")
    answer = extract(api, engagement_id)
    assert answer["status"] == "incomplete"
    assert "no thresholds have been set" in answer["incomplete_because"][0]
    assert answer["threshold"] is None
    # It cannot be shown not to be above PM, so it is named, as undetermined.
    assert answer["named_individually"] == []
    assert [(row["ref"], row["reason"]) for row in answer["undetermined"]] == [
        ("M-1", "no thresholds have been set")
    ]
    assert answer["undetermined"][0]["profit_before_tax"] == "-300000.00"
    assert answer["opinion_effect"]["unmodified_opinion"] == "undetermined"
    # The gate's own two reasons, as the opinion gate endpoint gives them.
    assert answer["opinion_effect"]["undetermined_because"] == [
        "no thresholds have been set",
        "M-1 is raised and cannot be banded",
    ]
    gate = api.get(f"/api/engagements/{engagement_id}/gates/opinion").json()
    assert answer["opinion_effect"]["undetermined_because"] == gate["undetermined_because"]
    assert answer["request"]["applies"] is True


def test_when_the_spine_cannot_be_read_nothing_is_guessed(api: TestClient) -> None:
    engagement_id, spine = ready(api)
    large = raise_item(api, engagement_id, "300000.00")
    small = raise_item(api, engagement_id, "20000.00")
    escalate(api, small["id"], "fraud", "Suspected")
    spine.unreachable = True
    answer = extract(api, engagement_id)
    assert answer["status"] == "incomplete"
    assert any("cannot be determined" in reason for reason in answer["incomplete_because"])
    # The large item cannot be banded: it is named as undetermined, never dropped.
    assert [(row["ref"], row["profit_before_tax"]) for row in answer["undetermined"]] == [
        ("M-1", None)
    ]
    assert "cannot be banded" in answer["undetermined"][0]["reason"]
    # The escalated item is still named, on its factor, with no figure made up for it.
    [named] = answer["named_individually"]
    assert (named["ref"], named["profit_before_tax"], named["band"]) == ("M-2", None, None)
    assert [reason["code"] for reason in named["reasons"]] == ["escalated"]
    assert named["lines"] == []
    assert answer["opinion_effect"]["unmodified_opinion"] == "undetermined"
    assert answer["totals"]["all_uncorrected"]["complete"] is False
    spine.unreachable = False
    assert refs(extract(api, engagement_id)["named_individually"]) == [large["ref"], small["ref"]]


# ---- read-only --------------------------------------------------------------------------------


def test_the_extract_is_read_only_and_writes_nothing(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    before = api.get(f"/api/engagements/{engagement_id}/events").json()
    first = extract(api, engagement_id)
    assert first["evaluation_run"] == {
        "status": "none",
        "detail": "no evaluation run has been recorded",
        "run_no": None,
    }
    assert extract(api, engagement_id) == first
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == before
    assert api.get(f"/api/engagements/{engagement_id}/evaluation/runs").json() == []
    for method in (api.post, api.put, api.delete):
        assert method(f"/api/engagements/{engagement_id}/tcwg-extract").status_code == 405
    assert api.get(f"/api/engagements/{uuid.uuid4()}/tcwg-extract").status_code == 404
    # Once a run records these figures, the extract says which.
    assert run(api, engagement_id).status_code == 201
    recorded = extract(api, engagement_id)["evaluation_run"]
    assert (recorded["status"], recorded["run_no"]) == ("current", 1)
    raise_item(api, engagement_id, "40000.00")
    assert extract(api, engagement_id)["evaluation_run"]["status"] == "stale"


# ---- the placing itself -------------------------------------------------------------------------


def _item(ref: str, amount: str | None, band: Band | None, **more: Any) -> gates.Item:
    value = None if amount is None else Decimal(amount)
    return gates.Item(
        misstatement_id=uuid.uuid4(),
        ref=ref,
        type=more.pop("type", "factual"),
        state=more.pop("state", "raised"),
        profit=value,
        net_assets=value,
        classification_only=False,
        band=band,
        **more,
    )


def test_every_uncorrected_item_falls_in_exactly_one_place() -> None:
    items = [
        _item("M-1", "-300000.00", Band.INDIVIDUALLY_SIGNIFICANT),
        _item("M-2", "-420000.00", Band.INDIVIDUALLY_SIGNIFICANT, state="refused"),
        _item("M-3", "-3000.00", Band.CLEARLY_TRIVIAL, escalated=True),
        _item("M-4", "-60000.00", Band.ACCUMULATED, type="projected"),
        _item("M-5", "-2000.00", Band.CLEARLY_TRIVIAL),
        _item("M-6", None, None),
        _item("M-7", "-500000.00", Band.INDIVIDUALLY_SIGNIFICANT, state="corrected"),
        _item("M-8", "-500000.00", Band.INDIVIDUALLY_SIGNIFICANT, state="withdrawn"),
        _item("M-9", None, None, escalated=True),
    ]
    total = gates.aggregate(items, Decimal("12500.00"))
    placed = tcwg.extract(items, total, Decimal("400000.00"))
    assert [(entry.item.ref, entry.reasons) for entry in placed.named] == [
        ("M-1", ("above_pm",)),
        ("M-2", ("above_pm", "at_or_above_om")),
        ("M-3", ("escalated",)),
        ("M-9", ("escalated",)),
    ]
    assert [item.ref for item in placed.undetermined] == ["M-6"]
    assert [item.ref for item in placed.other] == ["M-4"]
    assert [item.ref for item in placed.left_out] == ["M-5"]
    assert placed.communicated == 6
    # Corrected and withdrawn items are nowhere, however large.
    everywhere = [entry.item.ref for entry in placed.named] + [
        item.ref for item in placed.undetermined + placed.other + placed.left_out
    ]
    assert "M-7" not in everywhere and "M-8" not in everywhere
    # Sums: gross with no netting, net signed, and only what is known.
    summed = tcwg.sums(entry.item for entry in placed.named)
    assert summed.count == 4
    assert summed.profit == tcwg.Pair(Decimal("723000.00"), Decimal("-723000.00"))
    grouped = tcwg.by_type(placed.other)
    assert [(kind, grouped[kind].count) for kind in tcwg.TYPES] == [
        ("factual", 0),
        ("judgemental", 0),
        ("projected", 1),
    ]
    # With no line for overall materiality nothing is marked against it.
    assert all(
        "at_or_above_om" not in entry.reasons for entry in tcwg.extract(items, total, None).named
    )


def test_opposing_items_are_not_netted_in_gross() -> None:
    items = [
        _item("M-1", "-60000.00", Band.ACCUMULATED),
        _item("M-2", "60000.00", Band.ACCUMULATED),
    ]
    summed = tcwg.sums(items)
    assert summed.profit == tcwg.Pair(Decimal("120000.00"), Decimal("0.00"))
