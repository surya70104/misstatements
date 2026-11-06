"""Stage 4 over the API (spec section 9 ``evaluation``; section 2, paragraphs 10, 11 and
15; section 4.1; acceptance 4; D43): the evaluation run as an append-only record of the
aggregate against a threshold version, both materiality tests shown, state-dependent
inclusion, the boundaries, unresolved effects, and what a run never stores.
Runs on the in-memory stand-in and the Spine double (D24)."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, update
from sqlalchemy.exc import OperationalError

from oak_misstatements.models import EvaluationRun
from oak_misstatements.models.guard import AppendOnlyViolation
from tests.conftest import act_as, use_spine
from tests.fake_spine import OPEN_VERSION_ID
from tests.test_api_evaluation import evaluation, linked, raise_item, thresholds
from tests.test_api_transitions import move

REASSESSED = {"materiality_reassessed": True}
RENT = [5, 3]  # Dr rent / Cr provisions: profit and net assets both down
EQUITY = [1, 9]  # Dr receivables / Cr general reserve: net assets up, profit untouched
BALANCE_SHEET = [1, 2]  # Dr receivables / Cr bank: classification only


def lines(pair: list[int], amount: str) -> list[dict[str, Any]]:
    return [{"line_no": pair[0], "dr": amount}, {"line_no": pair[1], "cr": amount}]


def run(api: TestClient, engagement_id: str, body: Any = REASSESSED, **kwargs: Any) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/evaluation/runs", json=body, **kwargs)


def runs(api: TestClient, engagement_id: str) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/evaluation/runs")
    assert answer.status_code == 200, answer.text
    return answer.json()


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 400,000 · PM 250,000 · CTT 12,500
    return engagement_id


def stored_runs(api: TestClient) -> int:
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        return int(session.scalar(select(func.count()).select_from(EvaluationRun)) or 0)


# ---- the run: what it records ----------------------------------------------------------------


def test_a_run_records_the_threshold_version_and_the_four_aggregates(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "100000.00")
    raise_item(api, engagement_id, "40000.00", lines=lines([3, 4], "40000.00"))  # profit up
    raise_item(api, engagement_id, "80000.00", lines=lines(EQUITY, "80000.00"))
    live = evaluation(api, engagement_id)
    assert live["latest_run"] == {
        "status": "none",
        "detail": "no evaluation run has been recorded",
        "run": None,
    }
    act_as(api, "manager@firm")
    answer = run(api, engagement_id)
    assert answer.status_code == 201, answer.text
    recorded = answer.json()
    assert recorded["run_no"] == 1
    assert recorded["evaluated_by"] == "manager@firm"
    assert recorded["materiality_reassessed"] is True
    assert recorded["threshold_id"] == live["threshold"]["id"]
    assert recorded["threshold_version_no"] == 1
    # Acceptance 4: gross and net, profit and net assets, each its own column.
    assert (recorded["agg_gross_pbt"], recorded["agg_net_pbt"]) == ("140000.00", "-60000.00")
    assert (recorded["agg_gross_na"], recorded["agg_net_na"]) == ("220000.00", "20000.00")
    assert recorded["agg_gross_pbt"] == live["aggregate"]["profit_before_tax"]["gross"]
    assert recorded["agg_net_na"] == live["aggregate"]["net_assets"]["net"]
    detail = recorded["detail"]
    assert detail["threshold"] == {
        "id": live["threshold"]["id"],
        "version_no": 1,
        "om": "400000.00",
        "pm": "250000.00",
        "ctt": "12500.00",
    }
    assert detail["figures"]["profit_before_tax"] == live["aggregate"]["profit_before_tax"]
    assert detail["counted"] == ["M-1", "M-2", "M-3"]
    assert detail["not_accumulated"] == []
    assert detail["spine"] == {"version_id": str(OPEN_VERSION_ID), "locked": False}
    assert detail["identity_mode"] == "dev"
    assert "F3" in detail["basis"]
    assert recorded["authorisation"]["enforced"] is False
    after = evaluation(api, engagement_id)["latest_run"]
    assert after["status"] == "current"
    assert after["run"]["id"] == recorded["id"]
    trail = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [(e["kind"], e["actor"]) for e in trail] == [("materiality_reassessed", "manager@firm")]
    assert trail[0]["payload"]["evaluation_run_id"] == recorded["id"]
    assert "paragraph 10" in trail[0]["payload"]["basis"]


def test_a_run_holds_labels_and_aggregates_and_never_a_single_items_amount(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "10000.00")
    raise_item(api, engagement_id, "7777.77", type="projected")
    recorded = run(api, engagement_id).json()
    assert recorded["detail"]["items"] == [
        {
            "ref": "M-1",
            "version_no": 1,
            "state": "raised",
            "type": "factual",
            "band": "clearly_trivial",
            "classification_only": False,
            "uncorrected": True,
            "escalated": False,
        },
        {
            "ref": "M-2",
            "version_no": 1,
            "state": "raised",
            "type": "projected",
            "band": "clearly_trivial",
            "classification_only": False,
            "uncorrected": True,
            "escalated": False,
        },
    ]
    # No key of any item names a Dr, a Cr, an effect or a measure.
    for item in recorded["detail"]["items"]:
        assert set(item) == {
            "ref",
            "version_no",
            "state",
            "type",
            "band",
            "classification_only",
            "uncorrected",
            "escalated",
        }
    assert "lines" not in recorded["detail"] and "items" not in recorded["detail"]["figures"]
    columns = {column.name for column in EvaluationRun.__table__.columns}
    assert columns == {
        "id",
        "engagement_id",
        "run_no",
        "threshold_id",
        "agg_gross_pbt",
        "agg_net_pbt",
        "agg_gross_na",
        "agg_net_na",
        "materiality_reassessed",
        "py_carried",
        "detail",
        "evaluated_by",
        "determination",
        "conclusion",
        "basis",
        "concluded_by",
        "at",
    }


# ---- SA 450 paragraph 10: the reassessment prompt ----------------------------------------


def test_materiality_must_be_reassessed_before_a_run_and_nothing_else_may_be_sent(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "10000.00")
    for body in ({}, {"materiality_reassessed": False}, {"materiality_reassessed": None}):
        refused = run(api, engagement_id, body)
        assert refused.status_code == 422, body
    extras: tuple[dict[str, Any], ...] = (
        {"agg_gross_pbt": "0.00"},
        {"agg_net_na": "1.00"},
        {"evaluated_by": "forged@firm"},
        {"threshold_id": str(uuid.uuid4())},
        {"conclusion": "not material"},
        {"detail": {}},
    )
    for extra in extras:
        refused = run(api, engagement_id, {**REASSESSED, **extra})
        assert refused.status_code == 422, extra
        assert "Extra inputs are not permitted" in refused.text
    assert stored_runs(api) == 0
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == []


def test_a_run_needs_an_identity_and_any_authenticated_identity_may_make_one(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    act_as(api, None)
    refused = run(api, engagement_id)
    assert refused.status_code == 503
    assert stored_runs(api) == 0
    settings = cast(FastAPI, api.app).state.settings
    settings.auth = "header"
    assert run(api, engagement_id).status_code == 401
    made = run(api, engagement_id, headers={"X-Authenticated-User": "senior@firm"})
    assert made.status_code == 201, made.text
    assert made.json()["evaluated_by"] == "senior@firm"
    assert made.json()["detail"]["identity_mode"] == "header"


# ---- multiple misstatements, every classification ----------------------------------------


def test_factual_judgemental_projected_and_classification_only_items_are_each_kept_apart(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "30000.00")
    raise_item(api, engagement_id, "20000.00", type="judgemental")
    raise_item(api, engagement_id, "50000.00", type="projected")
    raise_item(api, engagement_id, "900000.00", lines=lines(BALANCE_SHEET, "900000.00"))
    recorded = run(api, engagement_id).json()
    assert recorded["agg_gross_pbt"] == "100000.00"
    assert recorded["agg_net_pbt"] == "-100000.00"
    profit = recorded["detail"]["figures"]["profit_before_tax"]
    assert (profit["factual_gross"], profit["judgemental_gross"], profit["projected_gross"]) == (
        "30000.00",
        "20000.00",
        "50000.00",
    )
    assert profit["gross_without_projected"] == "50000.00"
    assert recorded["detail"]["projected"] == ["M-3"]
    assert recorded["detail"]["classification_only"] == ["M-4"]  # listed, at nil
    assert [item["type"] for item in recorded["detail"]["items"]] == [
        "factual",
        "judgemental",
        "projected",
        "factual",
    ]
    assert [item["band"] for item in recorded["detail"]["items"]] == [
        "accumulated",
        "accumulated",
        "accumulated",
        "clearly_trivial",
    ]


# ---- state-dependent inclusion and exclusion --------------------------------------------


def test_corrected_and_withdrawn_items_leave_the_aggregate_and_refused_ones_stay(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    kept = raise_item(api, engagement_id, "15000.00")
    corrected = raise_item(api, engagement_id, "20000.00")
    refused = raise_item(api, engagement_id, "30000.00")
    withdrawn = raise_item(api, engagement_id, "40000.00")
    first = run(api, engagement_id).json()
    assert first["agg_gross_pbt"] == "105000.00"
    for record in (corrected, refused, withdrawn):
        assert move(api, record["id"], "communicated").status_code == 201
    assert move(api, corrected["id"], "corrected").status_code == 201
    assert move(api, refused["id"], "refused", "management disagrees").status_code == 201
    assert move(api, withdrawn["id"], "withdrawn", "raised in error").status_code == 201
    stale = evaluation(api, engagement_id)["latest_run"]
    assert stale["status"] == "stale"
    assert "raised, moved or re-banded" in stale["detail"]
    second = run(api, engagement_id).json()
    assert second["run_no"] == 2
    assert second["agg_gross_pbt"] == "45000.00"  # the raised item and the refused one
    assert second["detail"]["counted"] == ["M-1", "M-3"]
    assert second["detail"]["excluded"] == [
        {"ref": "M-2", "state": "corrected"},
        {"ref": "M-4", "state": "withdrawn"},
    ]
    assert [
        (i["ref"], i["version_no"], i["state"], i["uncorrected"]) for i in second["detail"]["items"]
    ] == [
        ("M-1", 1, "raised", True),
        ("M-2", 3, "corrected", False),
        ("M-3", 3, "refused", True),
        ("M-4", 3, "withdrawn", False),
    ]
    assert kept["ref"] == "M-1"
    # The earlier run is exactly as it was recorded.
    assert api.get(f"/api/evaluation-runs/{first['id']}").json()["agg_gross_pbt"] == "105000.00"
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "current"


# ---- the boundaries and the two tests ----------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "hard", "soft", "band", "significant", "at_om"),
    [
        ("12499.99", "clear", "clear", "clearly_trivial", [], []),
        ("12500.00", "clear", "clear", "accumulated", [], []),
        ("250000.00", "clear", "fires", "accumulated", [], []),
        ("250000.01", "clear", "fires", "individually_significant", ["M-1"], []),
        ("399999.99", "clear", "fires", "individually_significant", ["M-1"], []),
        ("400000.00", "fires", "fires", "individually_significant", ["M-1"], ["M-1"]),
    ],
)
def test_a_run_records_both_tests_at_every_boundary(
    api: TestClient,
    amount: str,
    hard: str,
    soft: str,
    band: str,
    significant: list[str],
    at_om: list[str],
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, amount)
    live = evaluation(api, engagement_id)
    assert live["tests"]["individual"]["individually_significant"] == significant
    assert live["tests"]["individual"]["at_or_above_om"] == at_om
    assert live["tests"]["aggregate"]["status"] == hard
    assert live["tests"]["aggregate"]["om"] == "400000.00"
    assert "paragraph 11" in live["tests"]["individual"]["basis"]
    # A gate that fires does not stop a run: the run records what was found.
    recorded = run(api, engagement_id)
    assert recorded.status_code == 201, recorded.text
    detail = recorded.json()["detail"]
    assert detail["gates"]["hard"]["status"] == hard
    assert detail["gates"]["soft"]["status"] == soft
    assert detail["items"][0]["band"] == band
    assert detail["tests"] == live["tests"]
    assert detail["sign_off"]["blocked"] is (soft == "fires" or bool(significant))
    # Spec section 4 (D53): below CTT the item is named and not accumulated; from CTT up
    # it is, and the aggregate is its amount.
    trivial = band == "clearly_trivial"
    assert recorded.json()["agg_gross_pbt"] == ("0.00" if trivial else amount)
    assert detail["not_accumulated"] == (["M-1"] if trivial else [])
    assert detail["counted"] == ([] if trivial else ["M-1"])


def test_a_refused_item_above_pm_stays_in_the_individual_test(api: TestClient) -> None:
    engagement_id = ready(api)
    record = raise_item(api, engagement_id, "300000.00")
    move(api, record["id"], "communicated")
    move(api, record["id"], "refused", "management will not adjust")
    live = evaluation(api, engagement_id)
    assert live["individually_significant"]["blocking"] == []  # the block is released...
    assert live["tests"]["individual"]["individually_significant"] == ["M-1"]  # ...the test is not
    corrected = raise_item(api, engagement_id, "300000.00")
    move(api, corrected["id"], "communicated")
    move(api, corrected["id"], "corrected")
    again = evaluation(api, engagement_id)["tests"]["individual"]
    assert again["individually_significant"] == ["M-1"]  # a corrected item is not uncorrected


def test_an_item_material_on_net_assets_alone_is_found_by_both_tests(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "400000.00", lines=lines(EQUITY, "400000.00"))
    live = evaluation(api, engagement_id)
    assert live["aggregate"]["profit_before_tax"]["gross"] == "0.00"
    assert live["tests"]["individual"]["at_or_above_om"] == ["M-1"]
    assert live["tests"]["aggregate"]["fires_on"] == ["net_assets.gross", "net_assets.net"]
    recorded = run(api, engagement_id).json()
    assert (recorded["agg_gross_pbt"], recorded["agg_gross_na"]) == ("0.00", "400000.00")


# ---- missing or unresolved effects: no run -------------------------------------------------


def test_no_run_is_recorded_without_thresholds(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    raise_item(api, engagement_id, "10000.00")
    refused = run(api, engagement_id)
    assert refused.status_code == 409
    assert "no thresholds have been set" in refused.json()["detail"]
    assert stored_runs(api) == 0
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == []


def test_no_run_is_recorded_while_an_effect_is_unresolved(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "10000.00")
    raise_item(api, engagement_id, "5000.00", lines=lines(EQUITY, "5000.00"))
    spine.rekey_ledger("Rent", "rent (indirect)")
    refused = run(api, engagement_id)
    assert refused.status_code == 409
    assert "the effects of M-1 cannot be determined" in refused.json()["detail"]
    assert "would be short" in refused.json()["detail"]
    spine.unreachable = True
    down = run(api, engagement_id)
    assert down.status_code == 409
    assert "M-1, M-2" in down.json()["detail"]
    assert stored_runs(api) == 0


def test_no_run_is_recorded_while_a_state_disagrees_with_the_spine(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    record = raise_item(api, engagement_id, "10000.00")
    adjustment_id = uuid.UUID(record["current"]["spine_adjustment_id"])
    spine.client().decide(OPEN_VERSION_ID, adjustment_id, status="accepted", note=None)
    refused = run(api, engagement_id)
    assert refused.status_code == 409
    assert "M-1 disagree with the Financial Spine" in refused.json()["detail"]
    assert stored_runs(api) == 0


def test_an_engagement_with_nothing_raised_can_still_be_evaluated(api: TestClient) -> None:
    engagement_id = ready(api)
    recorded = run(api, engagement_id).json()
    assert [
        recorded[key] for key in ("agg_gross_pbt", "agg_net_pbt", "agg_gross_na", "agg_net_na")
    ] == ["0.00"] * 4
    assert recorded["detail"]["items"] == []
    assert recorded["detail"]["sign_off"]["blocked"] is False


# ---- versioned thresholds and the history of runs ----------------------------------------


def test_each_run_keeps_the_threshold_version_it_was_made_against(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "100000.00")
    first = run(api, engagement_id).json()
    assert first["detail"]["items"][0]["band"] == "accumulated"
    revised = thresholds(api, engagement_id, om="150000.00", pm="90000.00")
    stale = evaluation(api, engagement_id)["latest_run"]
    assert stale["status"] == "stale"
    assert "thresholds have been revised" in stale["detail"]
    assert stale["run"]["id"] == first["id"]
    second = run(api, engagement_id).json()
    assert (second["run_no"], second["threshold_version_no"]) == (2, 2)
    assert second["threshold_id"] == revised["id"] != first["threshold_id"]
    assert second["detail"]["items"][0]["band"] == "individually_significant"  # re-banded
    assert second["detail"]["gates"]["soft"]["status"] == "fires"
    assert second["agg_gross_pbt"] == first["agg_gross_pbt"] == "100000.00"
    history = runs(api, engagement_id)
    assert [entry["run_no"] for entry in history] == [2, 1]
    # The first run is unchanged, still pointing at the superseded version it used.
    old = api.get(f"/api/evaluation-runs/{first['id']}").json()
    old.pop("authorisation")
    first.pop("authorisation")
    assert old == first
    assert api.get(f"/api/thresholds/{first['threshold_id']}").json()["is_current"] is False
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "current"


def test_a_lower_ctt_brings_an_item_into_the_next_run_and_leaves_the_last_as_it_was(
    api: TestClient,
) -> None:
    """Acceptance 2 with spec section 4 (D53): a revision recomputes every band, so an item
    that was clearly trivial is accumulated from then on. The run made before the revision
    is stale and still says what it left out."""
    engagement_id = ready(api)  # CTT 12,500
    raise_item(api, engagement_id, "60000.00")
    raise_item(api, engagement_id, "8000.00")
    first = run(api, engagement_id).json()
    assert first["agg_gross_pbt"] == "60000.00"
    assert (first["detail"]["counted"], first["detail"]["not_accumulated"]) == (["M-1"], ["M-2"])
    memo = first["detail"]["not_accumulated_total"]
    assert (memo["profit_before_tax_gross"], memo["at_or_above_ctt"]) == ("8000.00", False)
    thresholds(api, engagement_id, ctt_fraction="0.02", basis="C-2")  # CTT 5,000
    stale = evaluation(api, engagement_id)["latest_run"]
    assert stale["status"] == "stale"
    assert "thresholds have been revised" in stale["detail"]
    second = run(api, engagement_id).json()
    assert second["agg_gross_pbt"] == "68000.00"
    assert (second["detail"]["counted"], second["detail"]["not_accumulated"]) == (
        ["M-1", "M-2"],
        [],
    )
    assert [item["band"] for item in second["detail"]["items"]] == ["accumulated", "accumulated"]
    assert second["detail"]["not_accumulated_total"]["profit_before_tax_gross"] == "0.00"
    old = api.get(f"/api/evaluation-runs/{first['id']}").json()
    assert (old["agg_gross_pbt"], old["detail"]["not_accumulated"]) == ("60000.00", ["M-2"])
    assert [item["band"] for item in old["detail"]["items"]] == ["accumulated", "clearly_trivial"]
    assert [entry["run_no"] for entry in runs(api, engagement_id)] == [2, 1]


def test_a_new_misstatement_makes_the_latest_run_stale(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "10000.00")
    run(api, engagement_id)
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "current"
    raise_item(api, engagement_id, "5000.00")
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "stale"


def test_runs_are_numbered_per_engagement(api: TestClient) -> None:
    use_spine(api)
    one, two = linked(api), linked(api)
    thresholds(api, one)
    thresholds(api, two)
    assert [run(api, one).json()["run_no"], run(api, one).json()["run_no"]] == [1, 2]
    assert run(api, two).json()["run_no"] == 1
    assert [entry["run_no"] for entry in runs(api, one)] == [2, 1]
    assert [entry["run_no"] for entry in runs(api, two)] == [1]


# ---- append-only, and errors ---------------------------------------------------------------


def test_a_run_is_never_changed_or_deleted(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "20000.00")
    recorded = run(api, engagement_id).json()
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        row = session.get(EvaluationRun, uuid.UUID(recorded["id"]))
        assert row is not None
        row.agg_gross_pbt = row.agg_gross_pbt * 0
        with pytest.raises(AppendOnlyViolation, match="never an update"):
            session.flush()
    with factory() as session:
        row = session.get(EvaluationRun, uuid.UUID(recorded["id"]))
        session.delete(row)
        with pytest.raises(AppendOnlyViolation, match="never deleted"):
            session.flush()
    with factory() as session:
        with pytest.raises(AppendOnlyViolation, match="UPDATE is not allowed"):
            session.execute(update(EvaluationRun).values(evaluated_by="x"))
        with pytest.raises(AppendOnlyViolation, match="DELETE is not allowed"):
            session.execute(delete(EvaluationRun))
    assert api.get(f"/api/evaluation-runs/{recorded['id']}").json()["agg_gross_pbt"] == "20000.00"


def test_unknown_engagements_and_runs_are_404(api: TestClient) -> None:
    use_spine(api)
    missing = uuid.uuid4()
    assert run(api, str(missing)).status_code == 404
    assert api.get(f"/api/engagements/{missing}/evaluation/runs").status_code == 404
    assert api.get(f"/api/evaluation-runs/{missing}").status_code == 404
    assert api.get("/api/evaluation-runs/not-a-uuid").status_code == 422


def test_a_failed_commit_records_no_run(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "10000.00")
    factory = cast(FastAPI, api.app).state.session_factory
    state = {"armed": True}

    def boom(_session: Any) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OperationalError("COMMIT", {}, Exception("connection lost at commit"))

    event.listen(factory, "before_commit", boom)
    failed = TestClient(api.app, raise_server_exceptions=False).post(
        f"/api/engagements/{engagement_id}/evaluation/runs", json=REASSESSED
    )
    assert failed.status_code == 503
    assert stored_runs(api) == 0
    assert runs(api, engagement_id) == []
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == []
    assert run(api, engagement_id).json()["run_no"] == 1


# ---- regression: Features 1 to 3 through the evaluation ------------------------------------


def test_regression_the_evaluation_answer_keeps_every_earlier_block(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "250000.00")
    live = evaluation(api, engagement_id)
    for key in (
        "engagement_id",
        "threshold",
        "aggregate",
        "gates",
        "individually_significant",
        "state_consistency",
        "sign_off",
        "items",
        "authorisation",
    ):
        assert key in live, key
    assert live["gates"]["soft"]["acknowledgement"]["status"] == "required"
    assert live["gates"]["strategy_trigger"]["status"] == "not_configured"
    assert live["sign_off"]["blocked"] is True
    # Recording a run changes nothing about the gates or the sign-off decision.
    run(api, engagement_id)
    after = evaluation(api, engagement_id)
    for key in ("aggregate", "gates", "individually_significant", "sign_off", "items", "tests"):
        assert after[key] == live[key], key
