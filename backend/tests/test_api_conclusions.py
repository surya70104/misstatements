"""Stage 5 over the API (spec sections 6.4, 7, 9 and 12; acceptance 6, 7 and 10; D45): the
conclusion as a new append-only evaluation row carrying its figures and threshold version,
the gates in the write path, the partner-only rule, the run reviewed, and the strategy
prompt. Runs on the in-memory stand-in and the Spine double (D24)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from oak_misstatements.models import EvaluationRun
from oak_misstatements.models.guard import AppendOnlyViolation
from tests.conftest import use_spine
from tests.test_api_evaluation import (
    PARTNER,
    SENIOR,
    acknowledge,
    evaluation,
    header_mode,
    linked,
    raise_item,
    thresholds,
)
from tests.test_api_transitions import move

REASSESSED = {"materiality_reassessed": True}
WORDS = "Uncorrected misstatements are not material, individually or in aggregate."
BASIS = "The aggregate is below performance materiality on every measure; see C-4."


def record(proxy: TestClient, engagement_id: str) -> Any:
    answer = proxy.post(
        f"/api/engagements/{engagement_id}/evaluation/runs", json=REASSESSED, headers=SENIOR
    )
    assert answer.status_code == 201, answer.text
    return answer.json()


def conclude(
    client: TestClient,
    engagement_id: str,
    kind: str,
    run_id: str | None,
    *,
    headers: Any = PARTNER,
    **overrides: Any,
) -> Any:
    body: dict[str, Any] = {
        "conclusion": WORDS,
        "basis": BASIS,
        "reviewed_run_id": run_id,
        **REASSESSED,
    }
    body.update(overrides)
    body = {key: value for key, value in body.items() if value is not ...}
    return client.post(
        f"/api/engagements/{engagement_id}/evaluation/conclusions/{kind}",
        json=body,
        headers=headers,
    )


def prepared(api: TestClient, *amounts: str) -> tuple[TestClient, str]:
    """An engagement with thresholds (OM 400,000 · PM 250,000 · CTT 12,500) and one raised
    factual item per amount, then the app in header mode behind the trusted proxy."""
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    for amount in amounts:
        raise_item(api, engagement_id, amount)
    return header_mode(api, roles=True), engagement_id


def refused_item(api: TestClient, engagement_id: str, amount: str) -> Any:
    """An item management refused to correct: uncorrected, and no longer blocking."""
    record_ = raise_item(api, engagement_id, amount)
    assert move(api, record_["id"], "communicated").status_code == 201
    assert move(api, record_["id"], "refused", "management will not adjust").status_code == 201
    return record_


def stored(api: TestClient) -> list[tuple[int, str | None]]:
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        rows = session.execute(
            select(EvaluationRun.run_no, EvaluationRun.determination).order_by(EvaluationRun.run_no)
        ).all()
    return [(row[0], row[1]) for row in rows]


# ---- a valid conclusion --------------------------------------------------------------------


def test_a_conclusion_is_a_new_row_carrying_its_figures_and_threshold_version(
    api: TestClient,
) -> None:
    proxy, engagement_id = prepared(api, "10000.00", "4000.00")
    reviewed = record(proxy, engagement_id)
    before = api.get(f"/api/evaluation-runs/{reviewed['id']}").json()
    assert (before["concluded"], before["determination"], before["conclusion"]) == (
        False,
        None,
        None,
    )
    answer = conclude(proxy, engagement_id, "not-material", reviewed["id"])
    assert answer.status_code == 201, answer.text
    row = answer.json()
    assert row["run_no"] == 2  # a new row, never the reviewed one
    assert row["id"] != reviewed["id"]
    assert row["concluded"] is True
    assert row["determination"] == "not_material"
    assert (row["conclusion"], row["basis"]) == (WORDS, BASIS)
    assert row["concluded_by"] == row["evaluated_by"] == "partner@firm"
    # Acceptance 10: it carries the figures it was based on, and the threshold version.
    for key in ("agg_gross_pbt", "agg_net_pbt", "agg_gross_na", "agg_net_na", "threshold_id"):
        assert row[key] == reviewed[key], key
    assert row["agg_gross_pbt"] == "14000.00"
    assert row["threshold_version_no"] == 1
    assert row["detail"]["reviewed_run"] == {"id": reviewed["id"], "run_no": 1}
    assert row["detail"]["figures"] == reviewed["detail"]["figures"]
    assert row["detail"]["items"] == reviewed["detail"]["items"]
    assert row["detail"]["identity_mode"] == "header"
    # The reviewed run is exactly as it was.
    assert api.get(f"/api/evaluation-runs/{reviewed['id']}").json() == before
    assert stored(api) == [(1, None), (2, "not_material")]
    live = evaluation(api, engagement_id)["conclusion"]
    assert live["status"] == "current"
    assert live["run"]["id"] == row["id"]
    listed = api.get(f"/api/engagements/{engagement_id}/evaluation/conclusions").json()
    assert [entry["run_no"] for entry in listed] == [2]
    trail = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [(e["kind"], e["actor"]) for e in trail] == [
        ("materiality_reassessed", "senior@firm"),
        ("materiality_reassessed", "partner@firm"),
        ("evaluation_concluded", "partner@firm"),
    ]
    assert trail[2]["payload"]["determination"] == "not_material"
    assert trail[2]["payload"]["reviewed_run_id"] == reviewed["id"]


# ---- acceptance 10: never empty --------------------------------------------------------------


def test_acceptance_10_the_conclusion_and_its_basis_cannot_be_empty(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    run_id = record(proxy, engagement_id)["id"]
    for overrides in (
        {"conclusion": ""},
        {"conclusion": "   "},
        {"conclusion": ...},
        {"conclusion": None},
        {"basis": ""},
        {"basis": " \t "},
        {"basis": ...},
        {"reviewed_run_id": ...},
        {"reviewed_run_id": "not-a-uuid"},
        {"materiality_reassessed": False},
        {"materiality_reassessed": ...},
    ):
        for kind in ("not-material", "material"):
            refused = conclude(proxy, engagement_id, kind, run_id, **overrides)
            assert refused.status_code == 422, (kind, overrides)
    assert stored(api) == [(1, None)]


def test_no_figure_role_or_actor_can_be_sent_with_a_conclusion(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    run_id = record(proxy, engagement_id)["id"]
    extras: tuple[dict[str, Any], ...] = (
        {"agg_gross_pbt": "0.00"},
        {"agg_net_na": "0.00"},
        {"threshold_id": str(uuid.uuid4())},
        {"determination": "not_material"},
        {"concluded_by": "someone@firm"},
        {"roles": ["engagement-partner"]},
        {"detail": {}},
    )
    for extra in extras:
        refused = conclude(proxy, engagement_id, "not-material", run_id, **extra)
        assert refused.status_code == 422, extra
        assert "Extra inputs are not permitted" in refused.text
    assert stored(api) == [(1, None)]


def test_the_database_rules_refuse_an_empty_or_half_made_conclusion(api: TestClient) -> None:
    """The CHECKs of migration 0009, as the stand-in enforces them from the model."""
    proxy, engagement_id = prepared(api, "10000.00")
    reviewed = record(proxy, engagement_id)
    factory = cast(FastAPI, api.app).state.session_factory

    def row(**fields: Any) -> EvaluationRun:
        values: dict[str, Any] = {
            "engagement_id": uuid.UUID(engagement_id),
            "run_no": 99,
            "threshold_id": uuid.UUID(reviewed["threshold_id"]),
            "agg_gross_pbt": Decimal("1.00"),
            "agg_net_pbt": Decimal("1.00"),
            "agg_gross_na": Decimal("1.00"),
            "agg_net_na": Decimal("1.00"),
            "materiality_reassessed": True,
            "detail": {},
            "evaluated_by": "partner@firm",
            "determination": "not_material",
            "conclusion": WORDS,
            "basis": BASIS,
            "concluded_by": "partner@firm",
        }
        values.update(fields)
        return EvaluationRun(**values)

    for fields in (
        {"conclusion": "   "},
        {"basis": ""},
        {"conclusion": None},
        {"basis": None},
        {"concluded_by": None},
        {"determination": None},
        {"determination": "immaterial"},
        {"concluded_by": "someone-else@firm"},
    ):
        with factory() as session:
            session.add(row(**fields))
            with pytest.raises(IntegrityError):
                session.flush()
    with factory() as session:
        session.add(row())  # the complete row is accepted
        session.flush()
        session.rollback()


# ---- the run reviewed ---------------------------------------------------------------------------


def test_a_conclusion_names_the_run_reviewed_and_is_refused_once_that_run_is_stale(
    api: TestClient,
) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    reviewed = record(proxy, engagement_id)
    raise_item(proxy, engagement_id, "5000.00", headers=SENIOR)  # the figures move
    stale = conclude(proxy, engagement_id, "not-material", reviewed["id"])
    assert stale.status_code == 409
    assert "run 1, the one reviewed, no longer describes the evaluation" in stale.json()["detail"]
    assert "Nothing was saved" in stale.json()["detail"]
    assert stored(api) == [(1, None)]
    fresh = record(proxy, engagement_id)
    saved = conclude(proxy, engagement_id, "not-material", fresh["id"])
    assert saved.status_code == 201, saved.text
    assert saved.json()["agg_gross_pbt"] == "15000.00"
    assert saved.json()["detail"]["reviewed_run"]["run_no"] == 2


def test_a_revised_threshold_makes_the_reviewed_run_stale_too(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    reviewed = record(proxy, engagement_id)
    revised = proxy.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "300000.00", "pm": "200000.00", "ctt_fraction": "0.05", "basis": "C-2"},
        headers=SENIOR,
    )
    assert revised.status_code == 201, revised.text
    stale = conclude(proxy, engagement_id, "not-material", reviewed["id"])
    assert stale.status_code == 409
    assert "the thresholds have been revised" in stale.json()["detail"]
    fresh = record(proxy, engagement_id)
    saved = conclude(proxy, engagement_id, "not-material", fresh["id"]).json()
    assert saved["threshold_id"] == revised.json()["id"]
    assert saved["threshold_version_no"] == 2


def test_an_unknown_run_or_another_engagements_run_is_refused(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    record(proxy, engagement_id)
    missing = conclude(proxy, engagement_id, "not-material", str(uuid.uuid4()))
    assert missing.status_code == 404
    other = proxy.post("/api/engagements", json={"label": "other"}, headers=SENIOR).json()["id"]
    proxy.post(
        f"/api/engagements/{other}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
        headers=SENIOR,
    )
    foreign = record(proxy, other)
    refused = conclude(proxy, engagement_id, "not-material", foreign["id"])
    assert refused.status_code == 409
    assert "belongs to another engagement" in refused.json()["detail"]
    assert conclude(proxy, str(uuid.uuid4()), "not-material", foreign["id"]).status_code == 404
    assert [entry for entry in stored(api) if entry[1] is not None] == []


# ---- acceptance 7: the hard gate, in the write path ----------------------------------------


@pytest.mark.parametrize(
    ("amount", "allowed"), [("399999.99", True), ("400000.00", False), ("400000.01", False)]
)
def test_acceptance_7_the_hard_gate_blocks_a_conclusion_of_not_material(
    api: TestClient, amount: str, allowed: bool
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    refused_item(api, engagement_id, amount)  # uncorrected, and not itself blocking
    proxy = header_mode(api, roles=True)
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    run_id = record(proxy, engagement_id)["id"]
    live = evaluation(api, engagement_id)
    assert live["conclusion"]["allowed"]["not_material"]["allowed"] is allowed
    assert live["conclusion"]["allowed"]["material"]["allowed"] is True
    answer = conclude(proxy, engagement_id, "not-material", run_id)
    if allowed:
        assert answer.status_code == 201, answer.text
        assert answer.json()["detail"]["gates"]["hard"]["status"] == "clear"
        return
    assert answer.status_code == 409
    assert (
        "hard gate: aggregate uncorrected misstatements at or above overall materiality"
        in (answer.json()["detail"])
    )
    assert stored(api) == [(1, None)]
    # The misstatements are material: that conclusion is what the gate leaves open.
    material = conclude(proxy, engagement_id, "material", run_id, conclusion="Material.")
    assert material.status_code == 201, material.text
    saved = material.json()
    assert saved["determination"] == "material"
    assert saved["detail"]["gates"]["hard"]["status"] == "fires"
    assert saved["detail"]["sign_off"]["blocked"] is True
    assert saved["agg_gross_pbt"] == amount


def test_the_hard_gate_fires_on_net_assets_alone(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    equity = raise_item(
        api,
        engagement_id,
        "400000.00",
        lines=[{"line_no": 1, "dr": "400000.00"}, {"line_no": 9, "cr": "400000.00"}],
    )
    move(api, equity["id"], "communicated")
    move(api, equity["id"], "refused", "management will not adjust")
    proxy = header_mode(api, roles=True)
    acknowledge(proxy, engagement_id, headers=PARTNER)
    run = record(proxy, engagement_id)
    assert (run["agg_gross_pbt"], run["agg_gross_na"]) == ("0.00", "400000.00")
    blocked = conclude(proxy, engagement_id, "not-material", run["id"])
    assert blocked.status_code == 409
    assert "net_assets.gross" in blocked.json()["detail"]


# ---- the soft gate and the partner's acknowledgement --------------------------------------


def test_the_soft_gate_blocks_not_material_until_the_partner_acknowledges(
    api: TestClient,
) -> None:
    proxy, engagement_id = prepared(api, "250000.00")  # exactly PM: fires, and not blocking
    run_id = record(proxy, engagement_id)["id"]
    blocked = conclude(proxy, engagement_id, "not-material", run_id)
    assert blocked.status_code == 409
    assert "the partner has not acknowledged these figures" in blocked.json()["detail"]
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    saved = conclude(proxy, engagement_id, "not-material", run_id)  # the run is still current
    assert saved.status_code == 201, saved.text
    assert saved.json()["detail"]["gates"]["soft"]["acknowledgement"] == "acknowledged"
    assert saved.json()["detail"]["sign_off"]["blocked"] is False


def test_an_acknowledgement_gone_stale_blocks_again(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "250000.00")
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    raise_item(proxy, engagement_id, "1000.00", headers=SENIOR)  # the figures move
    run_id = record(proxy, engagement_id)["id"]
    blocked = conclude(proxy, engagement_id, "not-material", run_id)
    assert blocked.status_code == 409
    assert "not acknowledged these figures" in blocked.json()["detail"]
    assert evaluation(api, engagement_id)["gates"]["soft"]["acknowledgement"]["status"] == "stale"
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    assert conclude(proxy, engagement_id, "not-material", run_id).status_code == 201
    # A revised threshold stales the acknowledgement as well.
    proxy.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "390000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-2"},
        headers=SENIOR,
    )
    again = record(proxy, engagement_id)["id"]
    stale = conclude(proxy, engagement_id, "not-material", again)
    assert stale.status_code == 409
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    assert conclude(proxy, engagement_id, "not-material", again).status_code == 201


def test_a_pm_gate_set_to_hard_blocks_not_material_whatever_is_acknowledged(
    api: TestClient,
) -> None:
    proxy, engagement_id = prepared(api, "250000.00")
    cast(FastAPI, api.app).state.settings.pm_gate = "hard"
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    run_id = record(proxy, engagement_id)["id"]
    blocked = conclude(proxy, engagement_id, "not-material", run_id)
    assert blocked.status_code == 409
    assert "OAK_PM_GATE" in blocked.json()["detail"]
    assert conclude(proxy, engagement_id, "material", run_id).status_code == 201


# ---- acceptance 6: an item above PM --------------------------------------------------------


def test_acceptance_6_an_item_above_pm_blocks_every_conclusion_until_it_is_dealt_with(
    api: TestClient,
) -> None:
    proxy, engagement_id = prepared(api, "300000.00")
    run_id = record(proxy, engagement_id)["id"]
    for kind in ("not-material", "material"):
        blocked = conclude(proxy, engagement_id, kind, run_id)
        assert blocked.status_code == 409, kind
        assert "M-1 is individually significant and raised" in blocked.json()["detail"]
    item_id = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]["id"]
    moved = proxy.post(
        f"/api/misstatements/{item_id}/transitions", json={"to": "communicated"}, headers=SENIOR
    )
    assert moved.status_code == 201
    still = conclude(proxy, engagement_id, "material", record(proxy, engagement_id)["id"])
    assert still.status_code == 409
    assert "individually significant and communicated" in still.json()["detail"]
    proxy.post(
        f"/api/misstatements/{item_id}/transitions",
        json={"to": "refused", "reason": "management will not adjust"},
        headers=SENIOR,
    )
    run_id = record(proxy, engagement_id)["id"]
    # Refused with a reason: the item no longer blocks. The soft gate still fires.
    material = conclude(proxy, engagement_id, "material", run_id)
    assert material.status_code == 201, material.text
    not_yet = conclude(proxy, engagement_id, "not-material", run_id)
    assert not_yet.status_code == 409
    assert "soft gate" in not_yet.json()["detail"]
    acknowledge(proxy, engagement_id, headers=PARTNER)
    assert conclude(proxy, engagement_id, "not-material", run_id).status_code == 201
    assert [entry[1] for entry in stored(api)][-2:] == ["material", "not_material"]


# ---- an evaluation that is not known ------------------------------------------------------


def test_no_conclusion_of_either_kind_on_an_unknown_evaluation(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    proxy = header_mode(api, roles=True)
    for kind in ("not-material", "material"):  # no thresholds at all
        refused = conclude(proxy, engagement_id, kind, str(uuid.uuid4()))
        assert refused.status_code == 409, kind
        assert "no thresholds have been set" in refused.json()["detail"]
    proxy.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
        headers=SENIOR,
    )
    raise_item(proxy, engagement_id, "10000.00", headers=SENIOR)
    run_id = record(proxy, engagement_id)["id"]
    spine.rekey_ledger("Rent", "rent (indirect)")  # the item's effects become unresolved
    for kind in ("not-material", "material"):
        refused = conclude(proxy, engagement_id, kind, run_id)
        assert refused.status_code == 409, kind
        assert "M-1 is raised and cannot be banded" in refused.json()["detail"]
    live = evaluation(api, engagement_id)["conclusion"]["allowed"]
    assert live["not_material"]["allowed"] is False and live["material"]["allowed"] is False
    assert stored(api) == [(1, None)]


def test_no_conclusion_while_a_state_disagrees_with_the_spine(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    item = raise_item(api, engagement_id, "10000.00")
    proxy = header_mode(api, roles=True)
    run_id = record(proxy, engagement_id)["id"]
    adjustment_id = uuid.UUID(item["current"]["spine_adjustment_id"])
    from tests.fake_spine import OPEN_VERSION_ID

    spine.client().decide(OPEN_VERSION_ID, adjustment_id, status="accepted", note=None)
    for kind in ("not-material", "material"):
        refused = conclude(proxy, engagement_id, kind, run_id)
        assert refused.status_code == 409, kind
        assert "its adjustment is accepted in the Financial Spine" in refused.json()["detail"]


# ---- who may conclude --------------------------------------------------------------------------


def test_in_dev_mode_no_conclusion_can_be_saved(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "10000.00")
    run = api.post(f"/api/engagements/{engagement_id}/evaluation/runs", json=REASSESSED).json()
    for kind in ("not-material", "material"):
        refused = conclude(api, engagement_id, kind, run["id"])  # the claim is sent, unread
        assert refused.status_code == 403, kind
        assert "unavailable" in refused.json()["detail"]
    assert stored(api) == [(1, None)]
    live = evaluation(api, engagement_id)
    assert live["authorisation"]["partner_actions"]["available"] is False
    assert "conclusion" in live["authorisation"]["partner_actions"]["actions"]


def test_only_a_partner_named_by_the_trusted_proxy_may_conclude(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    run_id = record(proxy, engagement_id)["id"]
    for kind in ("not-material", "material"):
        assert conclude(proxy, engagement_id, kind, run_id, headers=SENIOR).status_code == 403
        missing = conclude(
            proxy, engagement_id, kind, run_id, headers={"X-Authenticated-User": "partner@firm"}
        )
        assert missing.status_code == 403
        assert "no role claim" in missing.json()["detail"]
        assert conclude(proxy, engagement_id, kind, run_id, headers={}).status_code == 401
        lookalike = conclude(
            proxy,
            engagement_id,
            kind,
            run_id,
            headers={
                "X-Authenticated-User": "x@firm",
                "X-Authenticated-Roles": "engagement-partner-assistant",
            },
        )
        assert lookalike.status_code == 403
        direct = TestClient(api.app, client=("203.0.113.9", 40000))  # not the proxy
        assert conclude(direct, engagement_id, kind, run_id).status_code == 401
    assert stored(api) == [(1, None)]
    saved = conclude(proxy, engagement_id, "not-material", run_id)
    assert saved.status_code == 201
    assert saved.json()["concluded_by"] == "partner@firm"


def test_a_non_partner_is_refused_before_any_gate_is_consulted(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "400000.00")  # every gate blocks
    run_id = record(proxy, engagement_id)["id"]
    for kind in ("not-material", "material"):
        assert conclude(proxy, engagement_id, kind, run_id, headers=SENIOR).status_code == 403
        assert conclude(proxy, engagement_id, kind, run_id).status_code == 409  # the partner


# ---- append-only history ---------------------------------------------------------------------


def test_a_revised_conclusion_is_another_row_and_no_row_is_ever_changed(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    reviewed = record(proxy, engagement_id)
    first = conclude(proxy, engagement_id, "not-material", reviewed["id"]).json()
    second = conclude(
        proxy,
        engagement_id,
        "material",
        reviewed["id"],
        conclusion="Material by nature.",
        basis="Relates to a covenant; see C-9.",
    ).json()
    assert (first["run_no"], second["run_no"]) == (2, 3)
    assert stored(api) == [(1, None), (2, "not_material"), (3, "material")]
    again = api.get(f"/api/evaluation-runs/{first['id']}").json()
    again.pop("authorisation")
    first.pop("authorisation")
    assert again == first  # the earlier conclusion is untouched
    listed = api.get(f"/api/engagements/{engagement_id}/evaluation/conclusions").json()
    assert [(entry["run_no"], entry["determination"]) for entry in listed] == [
        (3, "material"),
        (2, "not_material"),
    ]
    assert evaluation(api, engagement_id)["conclusion"]["run"]["id"] == second["id"]
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        row = session.get(EvaluationRun, uuid.UUID(first["id"]))
        assert row is not None
        row.conclusion = "rewritten"
        with pytest.raises(AppendOnlyViolation, match="never an update"):
            session.flush()
    with factory() as session:
        row = session.get(EvaluationRun, uuid.UUID(reviewed["id"]))
        assert row is not None
        row.determination, row.conclusion, row.basis, row.concluded_by = (
            "not_material",
            "added later",
            "added later",
            row.evaluated_by,
        )
        with pytest.raises(AppendOnlyViolation, match="never an update"):
            session.flush()  # a run can never be given a conclusion afterwards
    with factory() as session, pytest.raises(AppendOnlyViolation, match="UPDATE is not allowed"):
        session.execute(update(EvaluationRun).values(basis="x"))


def test_a_conclusion_goes_stale_when_the_evaluation_moves(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    run_id = record(proxy, engagement_id)["id"]
    saved = conclude(proxy, engagement_id, "not-material", run_id).json()
    assert evaluation(api, engagement_id)["conclusion"]["status"] == "current"
    raise_item(proxy, engagement_id, "5000.00", headers=SENIOR)
    live = evaluation(api, engagement_id)["conclusion"]
    assert live["status"] == "stale"
    assert "out of date" in live["detail"]
    assert live["run"]["id"] == saved["id"]  # still readable, never edited
    assert api.get(f"/api/evaluation-runs/{saved['id']}").json()["agg_gross_pbt"] == "10000.00"


def test_a_failed_commit_saves_no_conclusion(api: TestClient) -> None:
    proxy, engagement_id = prepared(api, "10000.00")
    run_id = record(proxy, engagement_id)["id"]
    factory = cast(FastAPI, api.app).state.session_factory
    state = {"armed": True}

    def boom(_session: Any) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OperationalError("COMMIT", {}, Exception("connection lost at commit"))

    event.listen(factory, "before_commit", boom)
    quiet = TestClient(api.app, raise_server_exceptions=False, client=("10.0.0.5", 40000))
    failed = conclude(quiet, engagement_id, "not-material", run_id)
    assert failed.status_code == 503
    assert stored(api) == [(1, None)]
    assert evaluation(api, engagement_id)["conclusion"]["status"] == "none"
    assert conclude(proxy, engagement_id, "not-material", run_id).status_code == 201
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(EvaluationRun)) == 2


# ---- the strategy trigger (spec section 7; SA 450 paragraph 6; pending B5) ---------------


def strategy(api: TestClient, engagement_id: str) -> Any:
    return evaluation(api, engagement_id)["gates"]["strategy_trigger"]


def respond(client: TestClient, engagement_id: str, **kwargs: Any) -> Any:
    return client.post(
        f"/api/engagements/{engagement_id}/evaluation/strategy-responses",
        json=kwargs.pop("json", {"strategy_revised": False, "note": "plan unchanged; see B-2"}),
        **kwargs,
    )


def test_without_a_declared_band_the_strategy_trigger_is_not_evaluated(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "399999.00")
    block = strategy(api, engagement_id)
    assert block["status"] == "not_configured"
    assert block["line"] is None and block["fraction"] is None
    assert "B5" in block["detail"] and "OAK_STRATEGY_TRIGGER_FRACTION" in block["detail"]
    refused = respond(api, engagement_id)
    assert refused.status_code == 409
    assert "nothing to answer" in refused.json()["detail"]


@pytest.mark.parametrize(("amount", "status"), [("299999.99", "clear"), ("300000.00", "fires")])
def test_the_strategy_trigger_fires_at_the_declared_fraction_of_om(
    api: TestClient, amount: str, status: str
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    cast(FastAPI, api.app).state.settings.strategy_trigger_fraction = Decimal("0.75")
    raise_item(api, engagement_id, amount)
    block = strategy(api, engagement_id)
    assert block["status"] == status
    assert (block["fraction"], block["line"]) == ("0.75", "300000.00")
    assert block["blocks"] is False
    assert block["response"]["status"] == ("required" if status == "fires" else "not_required")


def test_the_answer_to_the_strategy_prompt_is_recorded_either_way_and_goes_stale(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    cast(FastAPI, api.app).state.settings.strategy_trigger_fraction = Decimal("0.75")
    raise_item(api, engagement_id, "300000.00")
    for body in ({}, {"note": "x"}, {"strategy_revised": True, "actor": "x"}):
        assert respond(api, engagement_id, json=body).status_code == 422
    answer = respond(api, engagement_id)
    assert answer.status_code == 201, answer.text
    recorded = answer.json()["strategy_response_event"]
    assert recorded["kind"] == "strategy_trigger_response"
    assert recorded["actor"] == "senior@firm"  # any authenticated identity
    assert recorded["payload"]["strategy_revised"] is False
    assert recorded["payload"]["line"] == "300000.00"
    assert strategy(api, engagement_id)["response"]["status"] == "recorded"
    assert respond(api, engagement_id).status_code == 409  # already answered on these figures
    raise_item(api, engagement_id, "1000.00")
    assert strategy(api, engagement_id)["response"]["status"] == "stale"
    revised = respond(api, engagement_id, json={"strategy_revised": True})
    assert revised.status_code == 201
    assert revised.json()["strategy_response_event"]["payload"]["strategy_revised"] is True
    # A prompt, never a block: it changes nothing about sign-off.
    live = evaluation(api, engagement_id)
    assert not any("strategy" in reason for reason in live["sign_off"]["reasons"])
