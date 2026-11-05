"""The closure work of 5 November 2026 (architecture D46): the two read-only gate endpoints
D18 approved, event kinds and payloads validated as D13 approved, and the read-only report
of orphan Spine proposals. Runs on the in-memory stand-in and the Spine double (D24)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, insert, select
from sqlalchemy.exc import IntegrityError, OperationalError

from oak_misstatements.core.banding import Band
from oak_misstatements.core.gates import (
    aggregate,
    blocking_items,
    gate,
    opinion_gate,
    sign_off,
    sign_off_gate,
    unbanded_items,
)
from oak_misstatements.models import Event, InvalidEvent
from oak_misstatements.models.event import EVENT_KINDS, REQUIRED_PAYLOAD, check_event
from tests.conftest import use_spine
from tests.fake_spine import OPEN_VERSION_ID
from tests.test_api_evaluation import (
    PARTNER,
    acknowledge,
    evaluation,
    header_mode,
    linked,
    raise_item,
    thresholds,
)
from tests.test_api_transitions import move
from tests.test_gates import LINES, item


def gates_of(api: TestClient, engagement_id: str) -> tuple[Any, Any]:
    opinion = api.get(f"/api/engagements/{engagement_id}/gates/opinion")
    block = api.get(f"/api/engagements/{engagement_id}/gates/sign-off")
    assert opinion.status_code == 200 and block.status_code == 200, (opinion.text, block.text)
    return opinion.json(), block.json()


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 400,000 · PM 250,000 · CTT 12,500
    return engagement_id


# ---- D18: the two gates, open, blocked or undetermined, with the figures ------------------


def test_both_gates_are_undetermined_without_thresholds(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    opinion, block = gates_of(api, engagement_id)
    for answer, name in ((opinion, "opinion"), (block, "sign-off")):
        assert answer["gate"] == name
        assert answer["status"] == "undetermined"
        assert answer["undetermined_because"] == ["no thresholds have been set"]
        assert answer["blocked_by"] == []
        assert answer["threshold"] is None
        assert answer["read_only"] is True
        assert answer["authorisation"]["enforced"] is False


def test_both_gates_are_open_on_a_small_complete_evaluation_and_carry_the_figures(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "10000.00")
    opinion, block = gates_of(api, engagement_id)
    for answer in (opinion, block):
        assert answer["status"] == "open"
        assert answer["blocked_by"] == [] and answer["undetermined_because"] == []
        assert answer["figures"]["profit_before_tax"]["gross"] == "10000.00"
        live = evaluation(api, engagement_id)["aggregate"]
        for measure in ("profit_before_tax", "net_assets"):
            assert answer["figures"][measure] == live[measure], measure
        assert answer["threshold"]["om"] == "400000.00" and answer["threshold"]["pm"] == "250000.00"
        assert answer["complete"] is True
        assert answer["conclusion"] == {"status": "none", "determination": None, "run_no": None}
    assert "unmodified opinion" in opinion["scope"]
    assert "acceptance 6 and 7" in block["scope"]


@pytest.mark.parametrize(
    ("amount", "opinion_status"), [("399999.99", "open"), ("400000.00", "blocked")]
)
def test_the_opinion_gate_follows_overall_materiality_exactly(
    api: TestClient, amount: str, opinion_status: str
) -> None:
    engagement_id = ready(api)
    record = raise_item(api, engagement_id, amount)
    move(api, record["id"], "communicated")
    move(api, record["id"], "refused", "management will not adjust")
    opinion, block = gates_of(api, engagement_id)
    assert opinion["status"] == opinion_status
    assert opinion["hard_gate"]["status"] == ("fires" if opinion_status == "blocked" else "clear")
    if opinion_status == "blocked":
        assert "at or above overall materiality" in opinion["blocked_by"][0]
    # The soft gate fires and is unacknowledged: sign-off is blocked either way, and the
    # opinion gate does not report that, which is the sign-off gate's to say.
    assert block["status"] == "blocked"
    assert any("soft gate" in reason for reason in block["blocked_by"])
    assert not any("soft gate" in reason for reason in opinion["blocked_by"])


def test_the_two_gates_differ_on_an_item_above_pm_and_on_the_acknowledgement(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "300000.00")  # above PM, below OM, still raised
    opinion, block = gates_of(api, engagement_id)
    assert opinion["status"] == "open"  # the size alone does not block an unmodified opinion
    assert block["status"] == "blocked"
    assert "M-1 is individually significant and raised" in block["blocked_by"]
    proxy = header_mode(api, roles=True)
    item_id = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]["id"]
    for body in ({"to": "communicated"}, {"to": "refused", "reason": "will not adjust"}):
        moved = proxy.post(
            f"/api/misstatements/{item_id}/transitions",
            json=body,
            headers={"X-Authenticated-User": "senior@firm"},
        )
        assert moved.status_code == 201
    assert gates_of(api, engagement_id)[1]["status"] == "blocked"  # the soft gate, unacknowledged
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    opinion, block = gates_of(api, engagement_id)
    assert (opinion["status"], block["status"]) == ("open", "open")
    assert block["soft_gate"]["acknowledgement"] == "acknowledged"


def test_a_pm_gate_set_to_hard_blocks_the_opinion_gate_at_performance_materiality(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "250000.00")
    assert gates_of(api, engagement_id)[0]["status"] == "open"
    cast(FastAPI, api.app).state.settings.pm_gate = "hard"
    opinion, block = gates_of(api, engagement_id)
    assert opinion["status"] == "blocked"
    assert "OAK_PM_GATE" in opinion["blocked_by"][0]
    assert block["status"] == "blocked"


def test_a_gate_that_depends_on_projected_items_says_so(api: TestClient) -> None:
    engagement_id = ready(api)
    record = raise_item(api, engagement_id, "400000.00", type="projected")
    move(api, record["id"], "communicated")
    move(api, record["id"], "refused", "management will not adjust")
    opinion, _block = gates_of(api, engagement_id)
    assert opinion["status"] == "blocked"
    assert "pending decision B8" in opinion["blocked_by"][0]
    assert opinion["hard_gate"]["depends_on_projected"] is True
    assert opinion["figures"]["profit_before_tax"]["gross_without_projected"] == "0.00"


def test_an_unknown_evaluation_is_undetermined_and_never_open(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "10000.00")
    spine.rekey_ledger("Rent", "rent (indirect)")
    opinion, block = gates_of(api, engagement_id)
    for answer in (opinion, block):
        assert answer["status"] == "undetermined"
        assert "M-1 is raised and cannot be banded" in answer["undetermined_because"]
        assert answer["complete"] is False
    spine.unreachable = True
    assert [g["status"] for g in gates_of(api, engagement_id)] == ["undetermined"] * 2


def test_blocked_wins_over_undetermined(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    big = raise_item(
        api,
        engagement_id,
        "500000.00",
        lines=[{"line_no": 6, "dr": "500000.00"}, {"line_no": 3, "cr": "500000.00"}],
    )
    move(api, big["id"], "communicated")
    move(api, big["id"], "refused", "management will not adjust")
    raise_item(api, engagement_id, "10000.00")
    spine.rekey_ledger("Rent", "rent (indirect)")  # the second item becomes unresolved
    opinion, block = gates_of(api, engagement_id)
    assert opinion["status"] == "blocked" and block["status"] == "blocked"
    assert opinion["undetermined_because"] and block["undetermined_because"]


def test_a_disputed_state_makes_both_gates_undetermined(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    record = raise_item(api, engagement_id, "10000.00")
    spine.client().decide(
        OPEN_VERSION_ID,
        uuid.UUID(record["current"]["spine_adjustment_id"]),
        status="accepted",
        note=None,
    )
    opinion, block = gates_of(api, engagement_id)
    assert opinion["status"] == "undetermined" and block["status"] == "undetermined"
    assert "accepted in the Financial Spine" in opinion["undetermined_because"][0]


def test_the_gate_endpoints_are_read_only_and_report_the_latest_conclusion(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "10000.00")
    for name in ("opinion", "sign-off"):
        path = f"/api/engagements/{engagement_id}/gates/{name}"
        for method in ("post", "put", "patch", "delete"):
            assert getattr(api, method)(path).status_code == 405, (name, method)
    assert api.get(f"/api/engagements/{uuid.uuid4()}/gates/opinion").status_code == 404
    assert api.get(f"/api/engagements/{uuid.uuid4()}/gates/sign-off").status_code == 404
    proxy = header_mode(api, roles=True)
    senior = {"X-Authenticated-User": "senior@firm"}
    run = proxy.post(
        f"/api/engagements/{engagement_id}/evaluation/runs",
        json={"materiality_reassessed": True},
        headers=senior,
    ).json()
    saved = proxy.post(
        f"/api/engagements/{engagement_id}/evaluation/conclusions/not-material",
        json={
            "conclusion": "Not material.",
            "basis": "Below PM.",
            "reviewed_run_id": run["id"],
            "materiality_reassessed": True,
        },
        headers=PARTNER,
    )
    assert saved.status_code == 201, saved.text
    opinion, _block = gates_of(api, engagement_id)
    assert opinion["conclusion"] == {
        "status": "current",
        "determination": "not_material",
        "run_no": 2,
    }
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(Event))
    gates_of(api, engagement_id)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == before


def test_the_gate_exposure_on_items_directly() -> None:
    def exposures(items: list[Any], *, pm_gate: str = "soft", acknowledged: bool = False) -> Any:
        total = aggregate(items)
        hard, soft = gate("hard", total, LINES.om), gate("soft", total, LINES.pm)
        unbanded = unbanded_items(items)
        decision = sign_off(
            hard,
            soft,
            pm_gate=pm_gate,  # type: ignore[arg-type]
            soft_acknowledged=acknowledged,
            blocking=blocking_items(items),
            unbanded=unbanded,
        )
        return (
            opinion_gate(hard, soft, pm_gate=pm_gate, unbanded=unbanded),  # type: ignore[arg-type]
            sign_off_gate(decision, hard, soft, unbanded=unbanded),
            decision,
        )

    opinion, block, decision = exposures([item("M-1", "-1000")])
    assert (opinion.status, block.status, decision.blocked) == ("open", "open", False)
    refused = item(
        "M-1", "-400000", band=Band.INDIVIDUALLY_SIGNIFICANT, state="refused", refusal_reason="no"
    )
    opinion, block, _decision = exposures([refused], acknowledged=True)
    assert (opinion.status, block.status) == ("blocked", "blocked")
    opinion, block, _decision = exposures([item("M-1", "-250000")], acknowledged=True)
    assert (opinion.status, block.status) == ("open", "open")
    opinion, block, _decision = exposures([item("M-1", "-250000")])
    assert (opinion.status, block.status) == ("open", "blocked")
    opinion, block, decision = exposures([item("M-1", "-1"), item("M-2", None, "0", band=None)])
    assert (opinion.status, block.status) == ("undetermined", "undetermined")
    # Sign-off blocked is never reported open, and open never while the decision blocks.
    assert decision.blocked is True
    none = gate("hard", aggregate([]), None)
    empty = sign_off(
        none,
        gate("soft", aggregate([]), None),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(),
        unbanded=(),
    )
    assert opinion_gate(none, none, pm_gate="soft").status == "undetermined"
    assert sign_off_gate(empty, none, none).status == "undetermined"


# ---- D13: event kinds and payloads -----------------------------------------------------------


def test_every_kind_the_module_writes_has_a_required_payload() -> None:
    assert set(REQUIRED_PAYLOAD) == set(EVENT_KINDS)
    for kind, required in REQUIRED_PAYLOAD.items():
        assert required, kind
        check_event(kind, dict.fromkeys(required))
        with pytest.raises(InvalidEvent, match="must carry"):
            check_event(kind, {})
    with pytest.raises(InvalidEvent, match="is not an event kind"):
        check_event("partner_approved", {})
    with pytest.raises(InvalidEvent, match="must be an object"):
        check_event("threshold_recompute", ["not", "an", "object"])


def test_no_event_of_an_unknown_kind_or_with_an_incomplete_payload_is_written(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    factory = cast(FastAPI, api.app).state.session_factory
    for kind, payload in (
        ("partner_approved", {"x": 1}),
        ("", {}),
        ("materiality_reassessed", {"run_no": 1}),
        ("soft_gate_acknowledged", {}),
    ):
        with factory() as session:
            session.add(
                Event(engagement_id=uuid.UUID(engagement_id), kind=kind, payload=payload, actor="x")
            )
            with pytest.raises(InvalidEvent):
                session.flush()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0


def test_the_kind_is_also_refused_by_the_tables_own_check(api: TestClient) -> None:
    """The CHECK of migration 0010, as the stand-in enforces it from the model: it holds
    even when the application's own validation is bypassed."""
    engagement_id = ready(api)
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        statement = insert(Event).values(
            id=uuid.uuid4(),
            engagement_id=uuid.UUID(engagement_id),
            kind="partner_approved",
            payload={},
            actor="x",
        )
        with pytest.raises(IntegrityError):
            session.execute(statement)


def test_every_event_the_services_write_passes_its_own_validation(api: TestClient) -> None:
    engagement_id = ready(api)
    thresholds(api, engagement_id, pm="240000.00")  # a revision: threshold_recompute
    raise_item(api, engagement_id, "300000.00")
    settings = cast(FastAPI, api.app).state.settings
    settings.strategy_trigger_fraction = Decimal("0.5")
    answered = api.post(
        f"/api/engagements/{engagement_id}/evaluation/strategy-responses",
        json={"strategy_revised": True},
    )
    assert answered.status_code == 201, answered.text
    api.post(
        f"/api/engagements/{engagement_id}/evaluation/runs", json={"materiality_reassessed": True}
    )
    trail = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [entry["kind"] for entry in trail] == [
        "threshold_recompute",
        "strategy_trigger_response",
        "materiality_reassessed",
    ]
    for entry in trail:
        check_event(entry["kind"], entry["payload"])


# ---- the orphan report ---------------------------------------------------------------------


def reconciliation(api: TestClient, engagement_id: str) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/spine-reconciliation")
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_a_clean_engagement_reconciles(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    raise_item(api, engagement_id, "10000.00")
    record = raise_item(api, engagement_id, "5000.00")
    move(api, record["id"], "communicated")
    move(api, record["id"], "corrected")
    report = reconciliation(api, engagement_id)
    assert report["status"] == "ok"
    assert report["clean"] is True
    assert report["orphans"] == [] and report["missing"] == [] and report["disagreements"] == []
    assert report["duplicated_references"] == []
    assert report["not_ours"] == 0
    assert report["spine_version_id"] == str(OPEN_VERSION_ID)
    assert not [call for call in spine.calls if call[0] != "GET" and "decision" in call[1]][1:]


def test_a_failed_commit_while_raising_leaves_an_orphan_the_report_finds(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    factory = cast(FastAPI, api.app).state.session_factory
    state = {"armed": True}

    def boom(_session: Any) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OperationalError("COMMIT", {}, Exception("connection lost at commit"))

    event.listen(factory, "before_commit", boom)
    failed = TestClient(api.app, raise_server_exceptions=False).post(
        f"/api/engagements/{engagement_id}/misstatements",
        json={
            "type": "factual",
            "description": "Rent not accrued",
            "raised_from": "wp",
            "source_ref": "E-4.2",
            "lines": [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}],
        },
    )
    assert failed.status_code == 503
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []
    report = reconciliation(api, engagement_id)
    assert report["clean"] is False
    (orphan,) = report["orphans"]
    assert orphan["finding_ref"] == "M-1"
    assert orphan["status"] == "proposed"
    assert orphan["working_paper_ref"] == "E-4.2"
    assert orphan["measure"] == "10000.00"
    assert orphan["adjustment_id"] == str(next(iter(spine.adjustments)))
    # The retry takes the same reference, so the Spine now holds it twice.
    retried = raise_item(api, engagement_id, "10000.00")
    assert retried["ref"] == "M-1"
    again = reconciliation(api, engagement_id)
    assert [entry["adjustment_id"] for entry in again["orphans"]] == [orphan["adjustment_id"]]
    assert again["duplicated_references"] == ["M-1"]
    assert again["missing"] == [] and again["disagreements"] == []
    # The report repaired nothing: the orphan is still proposed in the Spine.
    assert spine.adjustments[uuid.UUID(orphan["adjustment_id"])].status == "proposed"
    assert not [call for call in spine.calls if "decision" in call[1]]


def test_the_report_lists_missing_adjustments_and_disputed_states(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    first = raise_item(api, engagement_id, "10000.00")
    second = raise_item(api, engagement_id, "5000.00")
    spine.client().decide(
        OPEN_VERSION_ID,
        uuid.UUID(first["current"]["spine_adjustment_id"]),
        status="accepted",
        note=None,
    )
    del spine.adjustments[uuid.UUID(second["current"]["spine_adjustment_id"])]
    report = reconciliation(api, engagement_id)
    assert report["clean"] is False
    assert report["disagreements"] == [
        {
            "ref": "M-1",
            "state": "raised",
            "expected_adjustment_status": "proposed",
            "adjustment_status": "accepted",
            "spine_adjustment_id": first["current"]["spine_adjustment_id"],
        }
    ]
    assert report["missing"] == [
        {
            "ref": "M-2",
            "state": "raised",
            "spine_adjustment_id": second["current"]["spine_adjustment_id"],
        }
    ]
    assert report["orphans"] == []


def test_adjustments_that_are_not_this_modules_are_counted_and_never_called_orphans(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    raise_item(api, engagement_id, "10000.00")
    lines = [{"line_no": 6, "dr": "100.00"}, {"line_no": 3, "cr": "100.00"}]
    for finding_ref in (None, "F-12", "M-1 (copy)", "XM-2"):
        spine.client().propose(
            OPEN_VERSION_ID,
            kind="correction",
            narration="entered in the Spine directly",
            working_paper_ref="E-9",
            finding_ref=finding_ref,
            lines=lines,
        )
    report = reconciliation(api, engagement_id)
    assert report["orphans"] == []
    assert report["not_ours"] == 4
    assert report["clean"] is True


def test_the_report_says_when_it_cannot_be_made(api: TestClient) -> None:
    unlinked = api.post("/api/engagements", json={"label": "no spine"}).json()["id"]
    assert reconciliation(api, unlinked)["status"] == "not_configured"
    spine = use_spine(api)
    assert reconciliation(api, unlinked)["status"] == "unpinned"
    engagement_id = linked(api)
    raise_item(api, engagement_id, "10000.00")
    spine.unreachable = True
    down = reconciliation(api, engagement_id)
    assert down["status"] == "unreachable"
    assert down["clean"] is None and down["orphans"] is None
    spine.unreachable = False
    spine.versions.pop(OPEN_VERSION_ID)
    assert reconciliation(api, engagement_id)["status"] == "missing"
    assert api.get(f"/api/engagements/{uuid.uuid4()}/spine-reconciliation").status_code == 404
    for method in ("post", "put", "delete"):
        assert (
            getattr(api, method)(
                f"/api/engagements/{engagement_id}/spine-reconciliation"
            ).status_code
            == 405
        )
