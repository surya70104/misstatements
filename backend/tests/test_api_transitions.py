"""Stage 3 over the API (spec section 3.3; acceptance 3 and 11; D41): the moves the
diagram draws, the dates and reasons, the append-only trail, what posts to the Spine and
what does not, and what happens when the Spine or the database fails part-way.
Runs on the in-memory stand-in and the Spine double (D24)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from oak_misstatements.models import MisstatementLineClass, MisstatementVersion
from tests.conftest import act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, OPEN_VERSION_ID, FakeSpine
from tests.test_api_evaluation import SAMPLING

RENT_ACCRUAL = [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}]
RENT_BEFORE = Decimal("60000.00")
PROVISION_BEFORE = Decimal("-80000.00")


def linked(api: TestClient) -> str:
    created = api.post(
        "/api/engagements",
        json={
            "label": "FY26",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def raise_one(api: TestClient, engagement_id: str, **overrides: Any) -> Any:
    body: dict[str, Any] = {
        "type": "factual",
        "description": "Rent for March not accrued",
        "raised_from": "wp",
        "source_ref": "E-4.2",
        "lines": RENT_ACCRUAL,
    }
    body.update(overrides)
    answer = api.post(f"/api/engagements/{engagement_id}/misstatements", json=body)
    assert answer.status_code == 201, answer.text
    return answer.json()


def move(api: TestClient, misstatement_id: str, to: str, reason: str | None = None) -> Any:
    body: dict[str, Any] = {"to": to}
    if reason is not None:
        body["reason"] = reason
    return api.post(f"/api/misstatements/{misstatement_id}/transitions", json=body)


def read(api: TestClient, misstatement_id: str) -> Any:
    answer = api.get(f"/api/misstatements/{misstatement_id}")
    assert answer.status_code == 200, answer.text
    return answer.json()


def decisions(spine: FakeSpine) -> list[tuple[str, str]]:
    return [call for call in spine.calls if call[1].endswith("/decision")]


def adjustment_of(spine: FakeSpine, record: Any) -> Any:
    return spine.adjustments[uuid.UUID(record["current"]["spine_adjustment_id"])]


def balances(spine: FakeSpine) -> tuple[Decimal, Decimal]:
    return (
        spine.adjusted_balance(OPEN_VERSION_ID, "Rent"),
        spine.adjusted_balance(OPEN_VERSION_ID, "Provision for expenses"),
    )


def setup(api: TestClient) -> tuple[FakeSpine, str, Any]:
    spine = use_spine(api)
    engagement_id = linked(api)
    return spine, engagement_id, raise_one(api, engagement_id)


def communicated(api: TestClient) -> tuple[FakeSpine, str, Any]:
    spine, engagement_id, record = setup(api)
    assert move(api, record["id"], "communicated").status_code == 201
    return spine, engagement_id, record


# ---- the valid moves ---------------------------------------------------------------------------


def test_communicating_records_the_date_in_a_new_version_and_asks_nothing_of_the_spine(
    api: TestClient,
) -> None:
    spine, _engagement, record = setup(api)
    answer = move(api, record["id"], "communicated")
    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert body["current"]["state"] == "communicated"
    assert body["current"]["version_no"] == 2
    assert body["current"]["communicated_at"] is not None
    assert body["current"]["decided_at"] is None
    assert body["transition"] == {
        "spine_decision": None,
        "decided_now": False,
        "note": None,
        "adjustment_status": None,
    }
    assert decisions(spine) == []
    assert adjustment_of(spine, record).status == "proposed"
    assert body["state_consistency"]["consistent"] is True
    first, second = body["versions"]
    assert (first["version_no"], first["state"], first["communicated_at"]) == (1, "raised", None)
    assert second["state"] == "communicated"


def test_acceptance_11_a_correction_posts_to_the_spine_and_moves_the_adjusted_balance(
    api: TestClient,
) -> None:
    spine, engagement_id, record = communicated(api)
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    act_as(api, "manager@firm")
    answer = move(api, record["id"], "corrected")
    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert body["current"]["state"] == "corrected"
    assert body["current"]["decided_at"] is not None
    assert body["current"]["communicated_at"] == body["versions"][1]["communicated_at"]
    assert body["current"]["refusal_reason"] is None
    assert body["transition"]["spine_decision"] == "accepted"
    assert body["transition"]["decided_now"] is True
    assert "M-1 corrected" in body["transition"]["note"]
    assert "manager@firm" in body["transition"]["note"]
    adjustment = adjustment_of(spine, record)
    assert adjustment.status == "accepted"
    assert adjustment.decision_note == body["transition"]["note"]
    assert body["spine"]["adjustment_status"] == "accepted"
    assert body["state_consistency"]["consistent"] is True
    # The adjusted trial balance moved by exactly the lines.
    assert balances(spine) == (RENT_BEFORE + Decimal("10000.00"), Decimal("-90000.00"))
    assert len(decisions(spine)) == 1
    # A corrected item is no longer uncorrected.
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["aggregate"]["excluded"] == [{"ref": "M-1", "state": "corrected"}]
    assert evaluation["aggregate"]["counted"] == []


def test_acceptance_11_an_uncorrected_misstatement_never_moves_the_adjusted_balance(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    raised = raise_one(api, engagement_id)
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    comm = raise_one(api, engagement_id)
    assert move(api, comm["id"], "communicated").status_code == 201
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    refused = raise_one(api, engagement_id)
    move(api, refused["id"], "communicated")
    assert move(api, refused["id"], "refused", "management disagrees").status_code == 201
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    withdrawn = raise_one(api, engagement_id)
    move(api, withdrawn["id"], "communicated")
    assert move(api, withdrawn["id"], "withdrawn", "raised in error").status_code == 201
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    assert [adjustment_of(spine, r).status for r in (raised, comm, refused, withdrawn)] == [
        "proposed",
        "proposed",
        "refused",
        "refused",
    ]


def test_a_refusal_records_its_reason_here_and_in_the_spine_and_stays_uncorrected(
    api: TestClient,
) -> None:
    spine, engagement_id, record = communicated(api)
    answer = move(api, record["id"], "refused", "  management considers it immaterial  ")
    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert body["current"]["state"] == "refused"
    assert body["current"]["refusal_reason"] == "management considers it immaterial"
    assert body["current"]["withdrawal_reason"] is None
    assert body["current"]["decided_at"] is not None
    adjustment = adjustment_of(spine, record)
    assert adjustment.status == "refused"
    assert "refused by management: management considers it immaterial" in adjustment.decision_note
    assert body["spine"]["decision_note"] == adjustment.decision_note
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["aggregate"]["counted"] == ["M-1"]  # refused is uncorrected (F3)
    assert evaluation["aggregate"]["profit_before_tax"]["gross"] == "10000.00"
    assert evaluation["state_consistency"]["inconsistent"] == []


def test_a_withdrawal_records_its_reason_is_excluded_and_can_never_post(api: TestClient) -> None:
    spine, engagement_id, record = communicated(api)
    answer = move(api, record["id"], "withdrawn", "duplicate of M-7")
    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert body["current"]["state"] == "withdrawn"
    assert body["current"]["withdrawal_reason"] == "duplicate of M-7"
    assert body["current"]["refusal_reason"] is None
    adjustment = adjustment_of(spine, record)
    assert adjustment.status == "refused"  # the Spine has no withdrawn status (B1)
    assert "WITHDRAWN by the auditor, not a management refusal: duplicate of M-7" in (
        adjustment.decision_note
    )
    # Decided once: the Spine can no longer accept it, so it can never post.
    with pytest.raises(Exception, match="cannot be changed"):
        spine.client().decide(
            OPEN_VERSION_ID, adjustment.adjustment_id, status="accepted", note=None
        )
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["aggregate"]["excluded"] == [{"ref": "M-1", "state": "withdrawn"}]
    assert evaluation["aggregate"]["profit_before_tax"]["gross"] == "0.00"
    # Kept: still in the schedule, with its whole trail.
    listed = api.get(f"/api/engagements/{engagement_id}/misstatements").json()
    assert [(row["ref"], row["current"]["state"]) for row in listed] == [("M-1", "withdrawn")]


def test_a_corrected_reclassification_posts_to_the_spines_reclass_column(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    record = raise_one(
        api, engagement_id, lines=[{"line_no": 1, "dr": "700.00"}, {"line_no": 2, "cr": "700.00"}]
    )
    move(api, record["id"], "communicated")
    assert move(api, record["id"], "corrected").status_code == 201
    assert adjustment_of(spine, record).kind == "reclass"
    assert spine.adjusted_balance(OPEN_VERSION_ID, "Alpha Traders") == Decimal("500700.00")
    assert spine.adjusted_balance(OPEN_VERSION_ID, "Kotak Bank") == Decimal("119300.00")


# ---- acceptance 3 and the reasons ---------------------------------------------------------


def test_acceptance_3_a_refusal_without_a_reason_is_rejected(api: TestClient) -> None:
    spine, _engagement, record = communicated(api)
    for body in (
        {"to": "refused"},
        {"to": "refused", "reason": ""},
        {"to": "refused", "reason": "   "},
    ):
        refused = api.post(f"/api/misstatements/{record['id']}/transitions", json=body)
        assert refused.status_code == 422, body
    missing = move(api, record["id"], "refused")
    assert "acceptance 3" in missing.text and "SA 450 paragraph 9" in missing.text
    assert read(api, record["id"])["current"]["state"] == "communicated"
    assert decisions(spine) == []
    assert adjustment_of(spine, record).status == "proposed"


def test_a_withdrawal_without_a_reason_is_rejected(api: TestClient) -> None:
    spine, _engagement, record = communicated(api)
    for body in ({"to": "withdrawn"}, {"to": "withdrawn", "reason": " "}):
        refused = api.post(f"/api/misstatements/{record['id']}/transitions", json=body)
        assert refused.status_code == 422, body
    assert "a withdrawal needs a reason" in move(api, record["id"], "withdrawn").text
    assert len(read(api, record["id"])["versions"]) == 2
    assert decisions(spine) == []


def test_a_reason_where_none_is_recorded_and_any_unknown_field_are_refused(
    api: TestClient,
) -> None:
    spine, _engagement, record = setup(api)
    with_reason = move(api, record["id"], "communicated", "sent the schedule")
    assert with_reason.status_code == 422
    assert "records no reason" in with_reason.text
    for extra in (
        {"created_by": "forged@firm"},
        {"communicated_at": "2020-01-01T00:00:00Z"},
        {"decided_at": "2020-01-01T00:00:00Z"},
        {"state": "corrected"},
        {"role": "partner"},
    ):
        refused = api.post(
            f"/api/misstatements/{record['id']}/transitions", json={"to": "communicated", **extra}
        )
        assert refused.status_code == 422, extra
        assert "Extra inputs are not permitted" in refused.text
    for bad in ("raised", "posted", "", None):
        assert (
            api.post(f"/api/misstatements/{record['id']}/transitions", json={"to": bad}).status_code
            == 422
        )
    assert read(api, record["id"])["current"]["state"] == "raised"
    assert decisions(spine) == []


# ---- invalid moves ---------------------------------------------------------------------------


@pytest.mark.parametrize("to", ["corrected", "refused", "withdrawn"])
def test_a_raised_item_must_be_communicated_first(api: TestClient, to: str) -> None:
    spine, _engagement, record = setup(api)
    refused = move(api, record["id"], to, "a reason" if to != "corrected" else None)
    assert refused.status_code == 409
    assert "the only move is to communicated" in refused.json()["detail"]
    assert "spec section 3.3" in refused.json()["detail"]
    assert len(read(api, record["id"])["versions"]) == 1
    assert decisions(spine) == []
    assert adjustment_of(spine, record).status == "proposed"


def test_a_communicated_item_cannot_be_communicated_again(api: TestClient) -> None:
    _spine, _engagement, record = communicated(api)
    again = move(api, record["id"], "communicated")
    assert again.status_code == 409
    assert "corrected or refused or withdrawn" in again.json()["detail"]
    assert len(read(api, record["id"])["versions"]) == 2


@pytest.mark.parametrize(
    ("final", "reason"),
    [("corrected", None), ("refused", "disagrees"), ("withdrawn", "in error")],
)
def test_nothing_follows_a_final_state(api: TestClient, final: str, reason: str | None) -> None:
    spine, _engagement, record = communicated(api)
    assert move(api, record["id"], final, reason).status_code == 201
    made = len(decisions(spine))
    balance = balances(spine)
    for to, why in (
        ("communicated", None),
        ("corrected", None),
        ("refused", "x"),
        ("withdrawn", "x"),
    ):
        refused = move(api, record["id"], to, why)
        assert refused.status_code == 409, to
        assert "final state" in refused.json()["detail"]
    after = read(api, record["id"])
    assert after["current"]["state"] == final
    assert len(after["versions"]) == 3
    assert len(decisions(spine)) == made
    assert balances(spine) == balance


def test_an_unknown_misstatement_is_404(api: TestClient) -> None:
    use_spine(api)
    assert move(api, str(uuid.uuid4()), "communicated").status_code == 404


# ---- the append-only trail -------------------------------------------------------------------


def test_every_move_is_a_new_version_and_no_earlier_version_changes(api: TestClient) -> None:
    spine, _engagement, record = setup(api)
    act_as(api, "senior@firm")
    v1 = read(api, record["id"])["versions"][0]
    act_as(api, "manager@firm")
    move(api, record["id"], "communicated")
    v2 = read(api, record["id"])["versions"][1]
    act_as(api, "partner@firm")
    move(api, record["id"], "refused", "will not book it")
    final = read(api, record["id"])
    assert [v["version_no"] for v in final["versions"]] == [1, 2, 3]
    assert [v["state"] for v in final["versions"]] == ["raised", "communicated", "refused"]
    assert final["versions"][0] == v1  # nothing about version 1 changed
    assert final["versions"][1] == v2
    # Who raised it never changes; who made each version is recorded on that version.
    assert [v["raised_by"] for v in final["versions"]] == ["senior@firm"] * 3
    assert [v["created_by"] for v in final["versions"]] == [
        "senior@firm",
        "manager@firm",
        "partner@firm",
    ]
    assert final["created_by"] == "senior@firm"
    # The fields a move does not touch are copied exactly.
    for field in (
        "type",
        "description",
        "raised_from",
        "source_ref",
        "spine_adjustment_id",
        "spine_kind",
    ):
        assert {v[field] for v in final["versions"]} == {v1[field]}, field
    assert final["versions"][2]["communicated_at"] == v2["communicated_at"]
    assert spine.adjustments  # the link is the same adjustment throughout
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MisstatementVersion)) == 3
        per_version = session.execute(
            select(MisstatementLineClass.misstatement_version_id, func.count()).group_by(
                MisstatementLineClass.misstatement_version_id
            )
        ).all()
        assert sorted(count for _id, count in per_version) == [2, 2, 2]  # each has its snapshot


def test_the_effects_and_the_type_fields_survive_every_move(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    record = raise_one(
        api, engagement_id, type="judgemental", range_low="5000.00", range_high="15000.00"
    )
    before = record["effects"]
    move(api, record["id"], "communicated")
    moved = move(api, record["id"], "refused", "estimate is theirs to make").json()
    assert moved["effects"] == before
    assert (moved["current"]["range_low"], moved["current"]["range_high"]) == (
        "5000.00",
        "15000.00",
    )
    projected = raise_one(
        api,
        engagement_id,
        type="projected",
        sample_ref="S-1",
        projection_basis="ratio",
        **SAMPLING,
        projected_amount="10000.00",
    )
    move(api, projected["id"], "communicated")
    kept = move(api, projected["id"], "withdrawn", "sample re-performed").json()
    assert (kept["current"]["sample_ref"], kept["current"]["projection_basis"]) == ("S-1", "ratio")
    assert kept["banding"]["projected"] is True


# ---- identity and the existing controls ------------------------------------------------------


def test_a_move_needs_an_identity_and_declares_the_authorisation_state(api: TestClient) -> None:
    spine, _engagement, record = setup(api)
    act_as(api, None)
    refused = move(api, record["id"], "communicated")
    assert refused.status_code == 503
    assert "No identity is configured" in refused.json()["detail"]
    act_as(api, "manager@firm")
    assert len(read(api, record["id"])["versions"]) == 1
    answer = move(api, record["id"], "communicated").json()
    assert answer["current"]["created_by"] == "manager@firm"
    assert answer["authorisation"]["enforced"] is False
    assert answer["authorisation"]["partner_actions"]["available"] is False
    assert decisions(spine) == []


def test_in_header_mode_the_proxys_identity_moves_the_state(api: TestClient) -> None:
    _spine, _engagement, record = setup(api)
    settings = cast(FastAPI, api.app).state.settings
    settings.auth = "header"
    settings.dev_user = None
    assert move(api, record["id"], "communicated").status_code == 401
    moved = api.post(
        f"/api/misstatements/{record['id']}/transitions",
        json={"to": "communicated"},
        headers={"X-Authenticated-User": "manager@firm"},
    )
    assert moved.status_code == 201, moved.text
    assert moved.json()["current"]["created_by"] == "manager@firm"


# ---- failure handling ------------------------------------------------------------------------


def test_a_spine_that_fails_at_the_decision_leaves_nothing_written_and_a_retry_works(
    api: TestClient,
) -> None:
    spine, _engagement, record = communicated(api)
    spine.decision_failure = 503
    failed = move(api, record["id"], "corrected")
    assert failed.status_code == 503
    assert len(read(api, record["id"])["versions"]) == 2
    assert read(api, record["id"])["current"]["state"] == "communicated"
    assert adjustment_of(spine, record).status == "proposed"
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:  # the rolled-back version left no snapshot rows either
        assert session.scalar(select(func.count()).select_from(MisstatementLineClass)) == 4
    spine.decision_failure = None
    assert move(api, record["id"], "corrected").status_code == 201
    assert adjustment_of(spine, record).status == "accepted"


def test_an_unreachable_or_unconfigured_spine_refuses_a_final_move_but_not_a_communication(
    api: TestClient,
) -> None:
    spine, _engagement, record = setup(api)
    spine.unreachable = True
    told = move(api, record["id"], "communicated")
    assert told.status_code == 201  # communicating asks nothing of the Spine
    assert told.json()["spine"]["status"] == "unreachable"
    assert told.json()["state_consistency"]["consistent"] is None
    for to, why in (("corrected", None), ("refused", "x"), ("withdrawn", "x")):
        assert move(api, record["id"], to, why).status_code == 503, to
    spine.unreachable = False
    cast(FastAPI, api.app).state.spine_client = None
    unconfigured = move(api, record["id"], "corrected")
    assert unconfigured.status_code == 409
    assert "no Financial Spine is configured" in unconfigured.json()["detail"]
    cast(FastAPI, api.app).state.spine_client = spine.client()
    assert len(read(api, record["id"])["versions"]) == 2
    assert adjustment_of(spine, record).status == "proposed"


def test_a_locked_spine_version_refuses_the_decision_and_nothing_is_written(
    api: TestClient,
) -> None:
    spine, _engagement, record = communicated(api)
    spine.versions[OPEN_VERSION_ID].is_locked = True
    for to, why in (("corrected", None), ("refused", "x"), ("withdrawn", "x")):
        refused = move(api, record["id"], to, why)
        assert refused.status_code == 409, to
        assert "locked" in refused.json()["detail"]
    assert len(read(api, record["id"])["versions"]) == 2
    assert adjustment_of(spine, record).status == "proposed"


def test_an_adjustment_the_spine_no_longer_has_is_404_and_nothing_is_written(
    api: TestClient,
) -> None:
    spine, _engagement, record = communicated(api)
    spine.adjustments.clear()
    missing = move(api, record["id"], "corrected")
    assert missing.status_code == 404
    assert len(read(api, record["id"])["versions"]) == 2


def test_a_database_failure_stops_the_move_before_the_spine_is_asked(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spine, _engagement, record = communicated(api)

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("INSERT", {}, Exception("disk full"))

    monkeypatch.setattr("oak_misstatements.services.transitions.copy_snapshot", broken)
    failed = move(api, record["id"], "corrected")
    assert failed.status_code == 503
    assert "Nothing was sent to the Financial Spine" in failed.json()["detail"]
    assert "disk full" in failed.json()["detail"]
    assert decisions(spine) == []
    assert adjustment_of(spine, record).status == "proposed"
    monkeypatch.undo()
    assert len(read(api, record["id"])["versions"]) == 2


def test_a_decision_taken_in_the_spine_directly_is_reported_blocks_and_can_be_completed(
    api: TestClient,
) -> None:
    spine, engagement_id, record = communicated(api)
    api.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    adjustment = adjustment_of(spine, record)
    spine.client().decide(OPEN_VERSION_ID, adjustment.adjustment_id, status="accepted", note=None)
    # The Spine posted it; this module still says communicated. Reported, never repaired.
    seen = read(api, record["id"])
    assert seen["current"]["state"] == "communicated"
    assert seen["state_consistency"]["consistent"] is False
    assert seen["state_consistency"]["expected_adjustment_status"] == "proposed"
    assert seen["state_consistency"]["adjustment_status"] == "accepted"
    assert "reconcile" in seen["state_consistency"]["detail"]
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["state_consistency"]["inconsistent"] == ["M-1"]
    assert evaluation["sign_off"]["blocked"] is True
    assert (
        "M-1 is communicated here but its adjustment is accepted in the Financial Spine"
        in evaluation["sign_off"]["reasons"]
    )
    # It cannot be refused or withdrawn: the Spine decides once and it is posted.
    for to in ("refused", "withdrawn"):
        refused = move(api, record["id"], to, "too late")
        assert refused.status_code == 409, to
        assert "decides once" in refused.json()["detail"]
    assert len(read(api, record["id"])["versions"]) == 2
    # Recording the correction completes the move without a second decision.
    made = len(decisions(spine))
    completed = move(api, record["id"], "corrected")
    assert completed.status_code == 201, completed.text
    assert completed.json()["transition"]["decided_now"] is False
    assert completed.json()["state_consistency"]["consistent"] is True
    assert len(decisions(spine)) == made
    after = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert after["state_consistency"]["inconsistent"] == []


def test_an_adjustment_the_spine_refused_cannot_be_recorded_as_corrected(api: TestClient) -> None:
    spine, _engagement, record = communicated(api)
    adjustment = adjustment_of(spine, record)
    spine.client().decide(OPEN_VERSION_ID, adjustment.adjustment_id, status="refused", note="no")
    refused = move(api, record["id"], "corrected")
    assert refused.status_code == 409
    assert (
        "decides once" in refused.json()["detail"]
        and "Nothing was written" in (refused.json()["detail"])
    )
    assert len(read(api, record["id"])["versions"]) == 2
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    # The refusal the Spine already holds can still be recorded here, with its reason.
    recorded = move(api, record["id"], "refused", "management refused in the meeting")
    assert recorded.status_code == 201
    assert recorded.json()["transition"]["decided_now"] is False


# ---- the gates follow the state --------------------------------------------------------------


def test_an_item_above_pm_blocks_until_it_is_corrected_refused_with_a_reason_or_withdrawn(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    api.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "900000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    big = [{"line_no": 5, "dr": "300000.00"}, {"line_no": 3, "cr": "300000.00"}]

    def blocking() -> list[str]:
        answer = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
        return cast(list[str], answer["individually_significant"]["blocking"])

    first = raise_one(api, engagement_id, lines=big)
    assert blocking() == ["M-1"]
    move(api, first["id"], "communicated")
    assert blocking() == ["M-1"]  # communicated still blocks (acceptance 6)
    move(api, first["id"], "refused", "management will not adjust")
    assert blocking() == []  # refused with a reason releases the item...
    total = api.get(f"/api/engagements/{engagement_id}/evaluation").json()["aggregate"]
    assert total["counted"] == ["M-1"]  # ...and it stays in the uncorrected aggregate
    second = raise_one(api, engagement_id, lines=big)
    move(api, second["id"], "communicated")
    move(api, second["id"], "withdrawn", "duplicate")
    third = raise_one(api, engagement_id, lines=big)
    move(api, third["id"], "communicated")
    assert blocking() == ["M-3"]
    move(api, third["id"], "corrected")
    assert blocking() == []
    total = api.get(f"/api/engagements/{engagement_id}/evaluation").json()["aggregate"]
    assert total["counted"] == ["M-1"]
    assert total["excluded"] == [
        {"ref": "M-2", "state": "withdrawn"},
        {"ref": "M-3", "state": "corrected"},
    ]
