"""The written representation attachment (SA 450 paragraph 14; spec section 2 row 14,
section 6 item 3; D63): the summary of uncorrected misstatements by type, its totals gross
and net on profit before tax and on net assets, the prior-period items, and the statement
management is asked to make. Read-only, and the same figures as the evaluation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from oak_misstatements.core import gates
from oak_misstatements.core import representation as core
from oak_misstatements.core.banding import Band
from tests.conftest import use_spine
from tests.test_api_conclusions import conclude, record, refused_item
from tests.test_api_evaluation import (
    SENIOR,
    evaluation,
    header_mode,
    linked,
    raise_item,
    thresholds,
)
from tests.test_api_evaluation_runs import run
from tests.test_api_tcwg import both, escalate, full_schedule, ready, refs
from tests.test_api_transitions import move

STATEMENT = (
    "Management and those charged with governance believe that the effects of the "
    "uncorrected misstatements summarised in this schedule are immaterial, individually and "
    "in aggregate, to the financial statements as a whole."
)


def attachment(api: TestClient, engagement_id: str, **kwargs: Any) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/rep-letter-attachment", **kwargs)
    assert answer.status_code == 200, answer.text
    return answer.json()


def codes(answer: Any) -> list[str]:
    return [caution["code"] for caution in answer["cautions"]]


def group(answer: Any, kind: str) -> Any:
    return next(entry for entry in answer["schedule"]["by_type"] if entry["type"] == kind)


# ---- the attachment ---------------------------------------------------------------------------


def test_the_attachment_lists_every_accumulated_uncorrected_misstatement_by_type(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    full_schedule(api, engagement_id)
    answer = attachment(api, engagement_id)

    assert [entry["type"] for entry in answer["schedule"]["by_type"]] == [
        "factual",
        "judgemental",
        "projected",
    ]
    assert refs(group(answer, "factual")["items"]) == ["M-1", "M-3", "M-4", "M-9"]
    assert refs(group(answer, "judgemental")["items"]) == ["M-2"]
    assert refs(group(answer, "projected")["items"]) == ["M-5"]
    assert answer["schedule"]["undetermined"] == []
    assert answer["schedule"]["count"] == 6
    # Each row: what it is, its state, and its two effects, separately.
    first = group(answer, "factual")["items"][0]
    assert (first["ref"], first["state"], first["description"]) == (
        "M-1",
        "raised",
        "factual item of 300000.00",
    )
    assert (first["profit_before_tax"], first["net_assets"]) == ("-300000.00", "-300000.00")
    # A refused item is still uncorrected, and carries management's own reason.
    refused = group(answer, "factual")["items"][3]
    assert (refused["state"], refused["refusal_reason"]) == (
        "refused",
        "Management considers it immaterial",
    )
    # Each type summed gross and net, on profit before tax and on net assets.
    assert {k: v for k, v in group(answer, "factual").items() if k not in ("items", "type")} == {
        "count": 4,
        **both("413000.00", "-413000.00", "413000.00", "-413000.00"),
    }
    assert group(answer, "judgemental")["profit_before_tax"] == {
        "gross": "420000.00",
        "net": "-420000.00",
    }
    assert group(answer, "projected")["net_assets"] == {"gross": "40000.00", "net": "-40000.00"}

    # Outside the summary: clearly trivial and not accumulated; corrected; withdrawn.
    outside = answer["not_included"]
    assert refs(outside["clearly_trivial"]["items"]) == ["M-6"]
    assert outside["not_uncorrected"] == [
        {"ref": "M-7", "state": "corrected"},
        {"ref": "M-8", "state": "withdrawn"},
    ]
    assert (answer["status"], answer["incomplete_because"]) == ("ready", [])
    assert answer["engagement"] == {"id": engagement_id, "label": "FY26"}
    assert answer["read_only"] is True
    assert "paragraph 14" in answer["basis"]


def test_the_statement_is_managements_belief_and_is_given_with_its_basis(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    representation = attachment(api, engagement_id)["representation"]
    assert representation["applies"] is True
    assert representation["text"] == STATEMENT
    assert "individually and in aggregate" in representation["text"]
    assert "SA 450 paragraph 14" in representation["basis"]
    assert "not the auditor's conclusion" in representation["basis"]


def test_with_nothing_accumulated_there_is_no_summary_and_no_statement(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    nothing = attachment(api, engagement_id)
    assert nothing["representation"]["applies"] is False
    assert "no summary to attach" in nothing["representation"]["text"]
    assert nothing["schedule"]["count"] == 0
    assert all(entry["items"] == [] for entry in nothing["schedule"]["by_type"])
    assert (nothing["status"], nothing["totals"]["count"]) == ("ready", 0)
    # Only a clearly trivial item, which is not accumulated: still nothing to represent on.
    raise_item(api, engagement_id, "2000.00")
    trivial = attachment(api, engagement_id)
    assert trivial["representation"]["applies"] is False
    assert refs(trivial["not_included"]["clearly_trivial"]["items"]) == ["M-1"]
    assert trivial["totals"]["profit_before_tax"]["gross"] == "0.00"


# ---- required totals --------------------------------------------------------------------------


def test_the_totals_are_gross_and_net_on_each_measure_and_the_types_add_up_to_them(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    full_schedule(api, engagement_id)
    answer = attachment(api, engagement_id)
    totals = answer["totals"]
    assert (totals["count"], totals["complete"]) == (6, True)
    for measure in ("profit_before_tax", "net_assets"):
        assert (totals[measure]["gross"], totals[measure]["net"]) == ("873000.00", "-873000.00")
        # The breakdown by type the aggregate itself carries is the breakdown listed.
        for kind in ("factual", "judgemental", "projected"):
            assert totals[measure][f"{kind}_gross"] == group(answer, kind)[measure]["gross"], kind
        for way in ("gross", "net"):
            added = sum(Decimal(entry[measure][way]) for entry in answer["schedule"]["by_type"])
            assert added == Decimal(totals[measure][way]), (measure, way)
    assert totals["profit_before_tax"]["gross_without_projected"] == "833000.00"
    assert sum(entry["count"] for entry in answer["schedule"]["by_type"]) == totals["count"]


def test_gross_does_not_net_opposing_misstatements_and_net_does(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")  # profit down
    raise_item(
        api,
        engagement_id,
        "60000.00",
        lines=[{"line_no": 3, "dr": "60000.00"}, {"line_no": 5, "cr": "60000.00"}],
    )  # the reverse: profit up
    answer = attachment(api, engagement_id)
    assert group(answer, "factual")["profit_before_tax"] == {"gross": "120000.00", "net": "0.00"}
    assert answer["totals"]["net_assets"]["gross"] == "120000.00"
    assert answer["totals"]["net_assets"]["net"] == "0.00"


# ---- consistency with the evaluation schedule -------------------------------------------------


def test_the_attachment_is_the_evaluations_own_schedule_and_figures(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    full_schedule(api, engagement_id)
    answer = attachment(api, engagement_id)
    live = evaluation(api, engagement_id)
    listed = [item["ref"] for entry in answer["schedule"]["by_type"] for item in entry["items"]]
    # Exactly the misstatements the aggregate counts: none more, none fewer.
    assert sorted(listed) == sorted(live["aggregate"]["counted"])
    assert (
        refs(answer["not_included"]["clearly_trivial"]["items"])
        == live["aggregate"]["not_accumulated"]
    )
    for measure in ("profit_before_tax", "net_assets"):
        assert answer["totals"][measure] == live["aggregate"][measure]
    # Each row's effects are the schedule's own.
    by_ref = {item["ref"]: item for item in live["items"]}
    for entry in answer["schedule"]["by_type"]:
        for item in entry["items"]:
            assert item["profit_before_tax"] == by_ref[item["ref"]]["profit_before_tax"]
            assert item["net_assets"] == by_ref[item["ref"]]["net_assets"]
    # And the same as the TCWG extract's totals of what it communicates.
    extract = api.get(f"/api/engagements/{engagement_id}/tcwg-extract").json()
    for measure in ("profit_before_tax", "net_assets"):
        assert answer["totals"][measure] == extract["totals"]["all_uncorrected"][measure]
    communicated = refs(extract["named_individually"]) + refs(extract["other_uncorrected"]["items"])
    assert sorted(listed) == sorted(communicated)


def test_the_attachment_follows_the_evaluation_and_a_recorded_run_never_changes(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    first = raise_item(api, engagement_id, "60000.00")
    assert move(api, first["id"], "communicated").status_code == 201
    recorded = run(api, engagement_id).json()
    answer = attachment(api, engagement_id)
    # While the run is current its four stored aggregates are the attachment's totals.
    assert answer["evaluation"]["run"] == {
        "status": "current",
        "detail": "the latest run describes the evaluation as it stands",
        "run_no": 1,
    }
    assert recorded["agg_gross_pbt"] == answer["totals"]["profit_before_tax"]["gross"]
    assert recorded["agg_net_pbt"] == answer["totals"]["profit_before_tax"]["net"]
    assert recorded["agg_gross_na"] == answer["totals"]["net_assets"]["gross"]
    assert recorded["agg_net_na"] == answer["totals"]["net_assets"]["net"]
    assert "no_current_run" not in codes(answer)

    # The evaluation moves on: the attachment moves with it and says the run is stale.
    raise_item(api, engagement_id, "40000.00")
    later = attachment(api, engagement_id)
    assert later["totals"]["profit_before_tax"]["gross"] == "100000.00"
    assert later["evaluation"]["run"]["status"] == "stale"
    assert "no_current_run" in codes(later)
    # The run recorded before is exactly as it was written.
    kept = api.get(f"/api/evaluation-runs/{recorded['id']}").json()
    assert kept["agg_gross_pbt"] == "60000.00" and kept == recorded | {
        "authorisation": kept["authorisation"]
    }


def test_the_attachment_is_read_only_and_writes_nothing(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    events = api.get(f"/api/engagements/{engagement_id}/events").json()
    schedule = api.get(f"/api/engagements/{engagement_id}/misstatements").json()
    first = attachment(api, engagement_id)
    assert attachment(api, engagement_id) == first
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == events
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == schedule
    assert api.get(f"/api/engagements/{engagement_id}/evaluation/runs").json() == []
    for method in (api.post, api.put, api.patch, api.delete):
        assert method(f"/api/engagements/{engagement_id}/rep-letter-attachment").status_code == 405
    assert api.get(f"/api/engagements/{uuid.uuid4()}/rep-letter-attachment").status_code == 404


# ---- prior-period items -----------------------------------------------------------------------


def test_prior_period_items_are_included_apart_from_the_totals(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    assert attachment(api, engagement_id)["prior_period"]["items"] == []
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
    answer = attachment(api, engagement_id)
    block = answer["prior_period"]
    assert refs(block["items"]) == ["PY-1"]
    assert block["items"][0]["current_period"] == {
        "profit_before_tax": "0.00",
        "net_assets": "-30000.00",
    }
    assert block["items"][0]["cumulative"] == {
        "profit_before_tax": "-30000.00",
        "net_assets": "-30000.00",
    }
    assert block["with_prior_period"]["cumulative"]["profit_before_tax"]["gross"] == "90000.00"
    assert block == evaluation(api, engagement_id)["prior_period"]
    # The current year's totals are not changed by it.
    assert answer["totals"]["profit_before_tax"]["gross"] == "60000.00"
    assert "prior_period_reaches" not in codes(answer)


def test_a_line_reached_only_with_prior_period_items_is_a_caution(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    item = raise_item(api, engagement_id, "200000.00")
    assert move(api, item["id"], "communicated").status_code == 201
    recorded = api.post(
        f"/api/engagements/{engagement_id}/prior-period",
        json={
            "description": "Depreciation understated in the prior year",
            "prior_period": "FY 2024-25",
            "source_ref": "PY schedule M-7",
            "current_profit_before_tax": "0.00",
            "current_net_assets": "0.00",
            "cumulative_profit_before_tax": "-60000.00",
            "cumulative_net_assets": "-60000.00",
            "basis": "Still stands at the year end",
        },
    )
    assert recorded.status_code == 201, recorded.text
    assert run(api, engagement_id).status_code == 201
    answer = attachment(api, engagement_id)
    assert codes(answer) == ["prior_period_reaches"]
    assert answer["cautions"][0]["text"] == (
        "with the prior-period items, a figure is at or above performance materiality on the "
        "cumulative basis, which the current year's aggregate alone does not reach; no gate "
        "tests this"
    )


# ---- the cautions: for the auditor, never part of the attachment ------------------------------


def test_the_cautions_say_where_the_evaluation_does_not_sit_with_the_statement(
    api: TestClient,
) -> None:
    engagement_id, _spine = ready(api)
    full_schedule(api, engagement_id)
    answer = attachment(api, engagement_id)
    assert codes(answer) == [
        "not_communicated",
        "named_individually",
        "opinion_blocked",
        "no_current_run",
    ]
    by_code = {caution["code"]: caution["text"] for caution in answer["cautions"]}
    # Raised items have not been communicated to management, so it cannot represent on them.
    assert by_code["not_communicated"].startswith("M-1, M-2, M-3, M-4, M-5 are raised")
    assert by_code["named_individually"].startswith("M-1, M-2, M-3 are above performance")
    assert "an unmodified opinion is blocked" in by_code["opinion_blocked"]
    assert "does not change this" in by_code["opinion_blocked"]
    assert by_code["no_current_run"] == "no evaluation run records these figures"
    # The statement is the same whatever the evaluation says: it is management's, not ours.
    assert answer["representation"]["text"] == STATEMENT
    assert answer["status"] == "ready"


def test_an_evaluation_that_sits_with_the_statement_raises_no_caution(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    item = raise_item(api, engagement_id, "60000.00")
    assert codes(attachment(api, engagement_id)) == ["not_communicated", "no_current_run"]
    assert move(api, item["id"], "communicated").status_code == 201
    assert run(api, engagement_id).status_code == 201
    answer = attachment(api, engagement_id)
    assert answer["cautions"] == []
    assert answer["evaluation"]["conclusion"] == {
        "status": "none",
        "determination": None,
        "run_no": None,
    }


def test_a_conclusion_that_the_misstatements_are_material_is_a_caution(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    refused_item(api, engagement_id, "450000.00")  # uncorrected, refused, at or above OM
    proxy = header_mode(api, roles=True)
    reviewed = record(proxy, engagement_id)
    assert conclude(proxy, engagement_id, "material", reviewed["id"]).status_code == 201
    answer = attachment(proxy, engagement_id, headers=SENIOR)
    assert "concluded_material" in codes(answer)
    assert answer["evaluation"]["conclusion"]["determination"] == "material"
    assert answer["evaluation"]["conclusion"]["status"] == "current"
    text = next(c["text"] for c in answer["cautions"] if c["code"] == "concluded_material")
    assert "the uncorrected misstatements are material" in text
    # The statement is still the one management is asked for; the caution is beside it.
    assert answer["representation"]["text"] == STATEMENT


# ---- an attachment that cannot be relied on says so ---------------------------------------------


def test_when_the_spine_cannot_be_read_the_items_are_named_and_no_figure_is_made_up(
    api: TestClient,
) -> None:
    engagement_id, spine = ready(api)
    raise_item(api, engagement_id, "60000.00")
    raise_item(api, engagement_id, "40000.00", type="projected")
    spine.unreachable = True
    answer = attachment(api, engagement_id)
    assert answer["status"] == "incomplete"
    assert answer["incomplete_because"] == [
        "the effects of M-1, M-2 cannot be determined, so the summary and its totals are short"
    ]
    assert [
        (row["ref"], row["profit_before_tax"]) for row in answer["schedule"]["undetermined"]
    ] == [
        ("M-1", None),
        ("M-2", None),
    ]
    assert all(entry["items"] == [] for entry in answer["schedule"]["by_type"])
    assert answer["totals"]["complete"] is False
    assert answer["schedule"]["count"] == 2
    assert "opinion_undetermined" in codes(answer)
    spine.unreachable = False
    assert attachment(api, engagement_id)["status"] == "ready"


def test_without_thresholds_the_attachment_is_incomplete(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    raise_item(api, engagement_id, "60000.00")
    answer = attachment(api, engagement_id)
    assert answer["status"] == "incomplete"
    assert "no thresholds have been set" in answer["incomplete_because"][0]
    assert answer["threshold"] is None
    # The item and its effects are still shown: only the evaluation cannot be made.
    assert refs(group(answer, "factual")["items"]) == ["M-1"]
    assert answer["totals"]["profit_before_tax"]["gross"] == "60000.00"
    thresholds(api, engagement_id)
    assert attachment(api, engagement_id)["status"] == "ready"


def test_an_escalated_item_below_the_threshold_is_in_the_summary(api: TestClient) -> None:
    engagement_id, _spine = ready(api)
    small = raise_item(api, engagement_id, "3000.00")
    assert attachment(api, engagement_id)["schedule"]["count"] == 0
    escalate(api, small["id"], "fraud", "Suspected override of controls")
    answer = attachment(api, engagement_id)
    assert refs(group(answer, "factual")["items"]) == ["M-1"]
    assert answer["not_included"]["clearly_trivial"]["items"] == []
    assert answer["totals"]["profit_before_tax"]["gross"] == "3000.00"
    assert "named_individually" in codes(answer)


# ---- the placing itself -------------------------------------------------------------------------


def _item(ref: str, amount: str | None, band: Band | None, **more: Any) -> gates.Item:
    value = None if amount is None else Decimal(amount)
    return gates.Item(
        misstatement_id=uuid.uuid4(),
        ref=ref,
        type=more.pop("type", "factual"),
        state=more.pop("state", "communicated"),
        profit=value,
        net_assets=value,
        classification_only=False,
        band=band,
        **more,
    )


def test_every_uncorrected_item_is_listed_undetermined_or_left_out() -> None:
    items = [
        _item("M-1", "-300000.00", Band.INDIVIDUALLY_SIGNIFICANT),
        _item("M-2", "-60000.00", Band.ACCUMULATED, type="projected", state="refused"),
        _item("M-3", "-2000.00", Band.CLEARLY_TRIVIAL),
        _item("M-4", None, None),
        _item("M-5", "-3000.00", Band.CLEARLY_TRIVIAL, escalated=True),
        _item("M-6", "-500000.00", Band.INDIVIDUALLY_SIGNIFICANT, state="corrected"),
        _item("M-7", "-500000.00", Band.INDIVIDUALLY_SIGNIFICANT, state="withdrawn"),
    ]
    total = gates.aggregate(items, Decimal("12500.00"))
    placed = core.summary(items, total)
    assert [item.ref for item in placed.listed] == ["M-1", "M-2", "M-5"]
    assert [item.ref for item in placed.undetermined] == ["M-4"]
    assert [item.ref for item in placed.left_out] == ["M-3"]
    # What is listed is exactly what the aggregate counts.
    assert tuple(item.ref for item in placed.listed) == total.counted
    assert "immaterial, individually and in aggregate" in core.REPRESENTATION_TEXT
