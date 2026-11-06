"""The qualitative checklist and escalation (spec sections 5 and 9; acceptance 8; D59): the
seven factors, a mandatory reason, entries that are appended and never changed, and an
escalated item listed individually and accumulated whatever its size."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from oak_misstatements.core import gates
from oak_misstatements.core.banding import Band
from oak_misstatements.core.qualitative import FACTOR_KEYS, FACTORS
from oak_misstatements.models.guard import AppendOnlyViolation
from oak_misstatements.models.qualitative import QualitativeFactor
from tests.conftest import act_as, use_spine
from tests.test_api_evaluation import evaluation, linked, raise_item, thresholds
from tests.test_api_evaluation_runs import run
from tests.test_api_transitions import move


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 4,00,000; PM 2,50,000; CTT 12,500
    return engagement_id


def checklist(api: TestClient, misstatement_id: str) -> Any:
    answer = api.get(f"/api/misstatements/{misstatement_id}/qualitative")
    assert answer.status_code == 200, answer.text
    return answer.json()


def record(api: TestClient, misstatement_id: str, factor: str, note: Any = "see E-12") -> Any:
    return api.post(
        f"/api/misstatements/{misstatement_id}/qualitative", json={"factor": factor, "note": note}
    )


def clear(api: TestClient, misstatement_id: str, factor: str, note: Any = "no longer so") -> Any:
    return api.post(
        f"/api/misstatements/{misstatement_id}/qualitative/{factor}/clear", json={"note": note}
    )


def schedule_row(api: TestClient, engagement_id: str, ref: str) -> Any:
    rows = api.get(f"/api/engagements/{engagement_id}/misstatements").json()
    return next(row for row in rows if row["ref"] == ref)


# ---- the checklist ----------------------------------------------------------------------------


def test_the_checklist_is_the_seven_factors_of_the_specification_in_its_order() -> None:
    assert FACTOR_KEYS == (
        "law_or_covenant",
        "earnings_trend",
        "ratio",
        "fraud",
        "related_party",
        "segment_or_remuneration",
        "loss_to_profit",
    )
    assert "loan covenant" in FACTORS["law_or_covenant"]
    assert "eleven Schedule III ratios" in FACTORS["ratio"]
    assert "suspected fraud" in FACTORS["fraud"]
    assert "related party" in FACTORS["related_party"]
    assert "management remuneration" in FACTORS["segment_or_remuneration"]
    assert "loss into a profit" in FACTORS["loss_to_profit"]


def test_a_new_misstatement_has_an_empty_checklist_and_is_not_escalated(api: TestClient) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    # The answer to raising is the record read on its own, so it carries the whole checklist.
    assert item["qualitative"]["escalated"] is False
    assert item["qualitative"]["factors"] == []
    assert item["qualitative"]["history"] == []
    answer = checklist(api, item["id"])
    assert answer["ref"] == "M-1"
    assert answer["escalated"] is False
    assert [entry["factor"] for entry in answer["checklist"]] == list(FACTOR_KEYS)
    assert [entry["text"] for entry in answer["checklist"]] == list(FACTORS.values())
    assert all(entry["applies"] is False and entry["note"] is None for entry in answer["checklist"])
    assert answer["history"] == []
    assert "section 5" in answer["escalation_basis"]
    assert answer["authorisation"]["enforced"] is False


# ---- acceptance 8 -----------------------------------------------------------------------------


def test_acceptance_8_an_escalated_item_is_listed_individually_regardless_of_its_size(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")  # M-1: accumulated, below PM
    small = raise_item(api, engagement_id, "3000.00")  # M-2: below CTT
    below_pm = raise_item(api, engagement_id, "40000.00")  # M-3: accumulated, below PM
    before = evaluation(api, engagement_id)
    assert before["tests"]["individual"]["escalated"] == []
    assert before["aggregate"]["not_accumulated"] == ["M-2"]
    assert before["aggregate"]["profit_before_tax"]["gross"] == "100000.00"

    act_as(api, "manager@firm")
    answer = record(api, small["id"], "related_party", "Sale to a director's firm; see E-12")
    assert answer.status_code == 201, answer.text
    assert answer.json()["escalated"] is True
    assert record(api, below_pm["id"], "fraud", "Suspected override of controls").status_code == 201

    after = evaluation(api, engagement_id)
    # Listed individually, by name, with the factors, whatever the band.
    assert after["tests"]["individual"]["escalated"] == [
        {"ref": "M-2", "factors": ["related_party"], "band": "clearly_trivial"},
        {"ref": "M-3", "factors": ["fraud"], "band": "accumulated"},
    ]
    assert after["aggregate"]["escalated"] == ["M-2", "M-3"]
    assert "acceptance 8" in after["tests"]["individual"]["escalation_basis"]
    # The band is still computed from the amount (spec section 4: "never chosen").
    assert [(i["ref"], i["band"], i["escalated"]) for i in after["items"]] == [
        ("M-1", "accumulated", False),
        ("M-2", "clearly_trivial", True),
        ("M-3", "accumulated", True),
    ]
    # An escalated item is never left out as clearly trivial: it is accumulated.
    assert after["aggregate"]["not_accumulated"] == []
    assert after["aggregate"]["counted"] == ["M-1", "M-2", "M-3"]
    assert after["aggregate"]["profit_before_tax"]["gross"] == "103000.00"
    # Escalation lists an item; it is not one of the gates of spec section 7.
    assert after["tests"]["individual"]["individually_significant"] == []
    assert after["sign_off"]["blocked"] is False
    # The schedule carries it too.
    row = schedule_row(api, engagement_id, "M-2")
    assert row["band"] == "clearly_trivial"
    assert row["qualitative"]["escalated"] is True
    assert [f["factor"] for f in row["qualitative"]["factors"]] == ["related_party"]
    assert row["qualitative"]["factors"][0]["note"] == "Sale to a director's firm; see E-12"
    assert row["qualitative"]["factors"][0]["escalated_by"] == "manager@firm"
    assert schedule_row(api, engagement_id, "M-1")["qualitative"] == {
        "escalated": False,
        "factors": [],
    }


def test_an_escalated_item_is_not_part_of_the_clearly_trivial_items_tested_together(
    api: TestClient,
) -> None:
    """D57 totals the clearly trivial items that are left out. An escalated one is already
    accumulated, so it is not in that total."""
    engagement_id = ready(api)
    first = raise_item(api, engagement_id, "7000.00")
    raise_item(api, engagement_id, "7000.00")  # 14,000 together: both would be accumulated
    assert evaluation(api, engagement_id)["aggregate"]["counted"] == ["M-1", "M-2"]
    assert record(api, first["id"], "ratio").status_code == 201
    total = evaluation(api, engagement_id)["aggregate"]
    assert total["counted"] == ["M-1"]  # escalated, so accumulated on its own
    assert total["not_accumulated"] == ["M-2"]  # 7,000 alone is below CTT
    assert total["not_accumulated_total"]["profit_before_tax_gross"] == "7000.00"
    assert total["profit_before_tax"]["gross"] == "7000.00"


def test_escalation_of_corrected_and_withdrawn_items_lists_nothing(api: TestClient) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    assert record(api, item["id"], "fraud").status_code == 201
    assert move(api, item["id"], "communicated").status_code == 201
    assert move(api, item["id"], "corrected").status_code == 201
    answer = evaluation(api, engagement_id)
    assert answer["tests"]["individual"]["escalated"] == []  # corrected: no longer uncorrected
    assert answer["aggregate"]["escalated"] == []
    assert answer["items"][0]["escalated"] is True  # the record itself stays escalated
    assert checklist(api, item["id"])["escalated"] is True


# ---- recording, updating and clearing -----------------------------------------------------------


def test_recording_updating_and_clearing_append_entries_and_never_change_one(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    act_as(api, "senior@firm")
    assert (
        record(
            api, item["id"], "law_or_covenant", "Breaches the current ratio covenant"
        ).status_code
        == 201
    )
    assert record(api, item["id"], "fraud", "Suspected").status_code == 201
    act_as(api, "manager@firm")
    updated = record(api, item["id"], "fraud", "Confirmed with the audit committee; see E-14")
    assert updated.status_code == 201, updated.text
    body = updated.json()
    by_factor = {entry["factor"]: entry for entry in body["checklist"]}
    assert by_factor["fraud"]["applies"] is True
    assert by_factor["fraud"]["note"] == "Confirmed with the audit committee; see E-14"
    assert by_factor["fraud"]["escalated_by"] == "manager@firm"
    assert by_factor["law_or_covenant"]["escalated_by"] == "senior@firm"
    assert by_factor["ratio"]["applies"] is False
    assert [(e["entry_no"], e["factor"], e["applies"]) for e in body["history"]] == [
        (1, "law_or_covenant", True),
        (2, "fraud", True),
        (3, "fraud", True),
    ]
    assert body["history"][1]["note"] == "Suspected"  # the earlier reason is kept

    cleared = clear(api, item["id"], "fraud", "Enquiry closed: an error, not a fraud")
    assert cleared.status_code == 201, cleared.text
    body = cleared.json()
    assert body["escalated"] is True  # the covenant factor still applies
    assert {e["factor"]: e["applies"] for e in body["checklist"]}["fraud"] is False
    assert body["history"][-1] == {
        "entry_no": 4,
        "factor": "fraud",
        "applies": False,
        "note": "Enquiry closed: an error, not a fraud",
        "escalated_by": "manager@firm",
        "at": body["history"][-1]["at"],
    }
    assert clear(api, item["id"], "law_or_covenant", "Waiver obtained").status_code == 201
    final = checklist(api, item["id"])
    assert final["escalated"] is False
    assert len(final["history"]) == 5  # nothing was removed
    assert schedule_row(api, engagement_id, "M-1")["qualitative"] == {
        "escalated": False,
        "factors": [],
    }
    assert evaluation(api, engagement_id)["tests"]["individual"]["escalated"] == []
    # A cleared factor can be recorded again.
    assert record(api, item["id"], "fraud", "Reopened").status_code == 201
    assert checklist(api, item["id"])["escalated"] is True


def test_clearing_the_last_factor_returns_a_clearly_trivial_item_to_being_left_out(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    small = raise_item(api, engagement_id, "3000.00")
    assert record(api, small["id"], "segment_or_remuneration").status_code == 201
    assert evaluation(api, engagement_id)["aggregate"]["counted"] == ["M-1"]
    assert clear(api, small["id"], "segment_or_remuneration").status_code == 201
    total = evaluation(api, engagement_id)["aggregate"]
    assert (total["counted"], total["not_accumulated"], total["escalated"]) == ([], ["M-1"], [])


@pytest.mark.parametrize("note", [None, "", "   "])
def test_a_factor_is_never_recorded_or_cleared_without_a_reason(api: TestClient, note: Any) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    assert record(api, item["id"], "fraud", note).status_code == 422
    assert checklist(api, item["id"])["history"] == []
    assert record(api, item["id"], "fraud", "Suspected").status_code == 201
    assert clear(api, item["id"], "fraud", note).status_code == 422
    assert checklist(api, item["id"])["escalated"] is True


def test_what_is_refused_and_writes_nothing(api: TestClient) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    base = f"/api/misstatements/{item['id']}/qualitative"
    # A factor that is not one of the seven.
    assert record(api, item["id"], "going_concern").status_code == 422
    unknown = clear(api, item["id"], "going_concern")
    assert unknown.status_code == 422 and "not a factor" in unknown.json()["detail"]
    # Who acted and when are never taken from the request.
    for extra in (
        {"escalated_by": "partner@firm"},
        {"at": "2026-01-01T00:00:00Z"},
        {"applies": False},
    ):
        forged = api.post(base, json={"factor": "fraud", "note": "x", **extra})
        assert forged.status_code == 422, extra
    # Clearing a factor that is not recorded.
    nothing = clear(api, item["id"], "fraud")
    assert nothing.status_code == 409 and "nothing to clear" in nothing.json()["detail"]
    # Recording the same factor again with the same reason.
    assert record(api, item["id"], "fraud", "Suspected").status_code == 201
    again = record(api, item["id"], "fraud", "Suspected")
    assert again.status_code == 409 and "already recorded" in again.json()["detail"]
    assert len(checklist(api, item["id"])["history"]) == 1
    # A misstatement that does not exist.
    missing = uuid.uuid4()
    assert api.get(f"/api/misstatements/{missing}/qualitative").status_code == 404
    assert record(api, str(missing), "fraud").status_code == 404
    assert clear(api, str(missing), "fraud").status_code == 404
    # An identity is required, as for every write: with none configured the write is refused.
    act_as(api, None)
    assert record(api, item["id"], "ratio").status_code == 503
    act_as(api, "senior@firm")
    assert len(checklist(api, item["id"])["history"]) == 1


def test_the_entries_cannot_be_changed_or_deleted(api: TestClient) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    assert record(api, item["id"], "fraud", "Suspected").status_code == 201
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        entry = session.scalars(select(QualitativeFactor)).one()
        entry.note = "rewritten"
        with pytest.raises(AppendOnlyViolation, match="never an update"):
            session.flush()
    with factory() as session:
        entry = session.scalars(select(QualitativeFactor)).one()
        session.delete(entry)
        with pytest.raises(AppendOnlyViolation, match="never deleted"):
            session.flush()
    with factory() as session:
        with pytest.raises(AppendOnlyViolation, match="UPDATE is not allowed"):
            session.execute(update(QualitativeFactor).values(applies=False))
        with pytest.raises(AppendOnlyViolation, match="DELETE is not allowed"):
            session.execute(delete(QualitativeFactor))
    assert checklist(api, item["id"])["history"][0]["note"] == "Suspected"


# ---- consistency with runs --------------------------------------------------------------------


def test_escalating_an_item_makes_the_latest_run_stale_and_the_next_run_records_it(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")
    small = raise_item(api, engagement_id, "3000.00")
    first = run(api, engagement_id).json()
    assert first["agg_gross_pbt"] == "60000.00"
    assert first["detail"]["escalated"] == []
    assert (
        record(
            api, small["id"], "loss_to_profit", "Turns the year's loss into a profit"
        ).status_code
        == 201
    )
    assert evaluation(api, engagement_id)["latest_run"]["status"] == "stale"
    second = run(api, engagement_id).json()
    assert second["agg_gross_pbt"] == "63000.00"
    assert second["detail"]["escalated"] == ["M-2"]
    assert second["detail"]["tests"]["individual"]["escalated"] == [
        {"ref": "M-2", "factors": ["loss_to_profit"], "band": "clearly_trivial"}
    ]
    assert [item["escalated"] for item in second["detail"]["items"]] == [False, True]
    # The earlier run is as it was recorded.
    old = api.get(f"/api/evaluation-runs/{first['id']}").json()
    assert (old["agg_gross_pbt"], old["detail"]["escalated"]) == ("60000.00", [])


# ---- the rule itself, on items ----------------------------------------------------------------


def test_an_escalated_item_accumulates_whatever_its_band() -> None:
    def item(
        ref: str, profit: str, *, band: Band, escalated: bool, state: str = "raised"
    ) -> gates.Item:
        from decimal import Decimal

        return gates.Item(
            misstatement_id=uuid.uuid4(),
            ref=ref,
            type="factual",
            state=state,
            profit=Decimal(profit),
            net_assets=Decimal(profit),
            classification_only=False,
            band=band,
            escalated=escalated,
        )

    from decimal import Decimal

    total = gates.aggregate(
        [
            item("M-1", "-3000", band=Band.CLEARLY_TRIVIAL, escalated=True),
            item("M-2", "-4000", band=Band.CLEARLY_TRIVIAL, escalated=False),
            item("M-3", "-5000", band=Band.CLEARLY_TRIVIAL, escalated=True, state="withdrawn"),
        ],
        Decimal("12500.00"),
    )
    assert total.counted == ("M-1",)
    assert total.not_accumulated == ("M-2",)
    assert total.escalated == ("M-1",)  # the withdrawn one is not uncorrected
    assert total.profit.gross == Decimal("3000")
    assert total.left_out_profit == Decimal("4000")


# ---- what one misstatement carries when it is read on its own --------------------------------


def test_one_misstatement_read_on_its_own_carries_the_whole_checklist(api: TestClient) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "20000.00")
    act_as(api, "manager@firm")
    assert record(api, item["id"], "fraud", "Suspected override of controls").status_code == 201
    assert clear(api, item["id"], "fraud", "Explained: see E-14").status_code == 201
    assert record(api, item["id"], "ratio", "Current ratio falls below 1").status_code == 201

    read = api.get(f"/api/misstatements/{item['id']}")
    assert read.status_code == 200, read.text
    carried = read.json()["qualitative"]
    listed = checklist(api, item["id"])
    # The same words as the checklist's own endpoint: one source, read two ways.
    assert carried == {
        key: listed[key]
        for key in ("escalated", "factors", "escalation_basis", "checklist", "history")
    }
    assert carried["escalated"] is True
    assert [row["factor"] for row in carried["checklist"]] == list(FACTOR_KEYS)
    assert [row["factor"] for row in carried["checklist"] if row["applies"]] == ["ratio"]
    assert [(e["factor"], e["applies"]) for e in carried["history"]] == [
        ("fraud", True),
        ("fraud", False),
        ("ratio", True),
    ]
    assert [factor["factor"] for factor in carried["factors"]] == ["ratio"]
    # A row of the schedule carries the summary alone.
    assert set(schedule_row(api, engagement_id, "M-1")["qualitative"]) == {"escalated", "factors"}
    # The answer to a move is the record as it now stands, so it carries the checklist too.
    moved = move(api, item["id"], "communicated")
    assert moved.status_code == 201, moved.text
    assert moved.json()["qualitative"] == carried
