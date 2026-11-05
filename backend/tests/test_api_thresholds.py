"""Thresholds over the API (spec section 4, section 9; acceptance 2's record; D26, D27, D29).
Runs on the in-memory stand-in when no test database is configured (D24)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import act_as, use_spine
from tests.fake_spine import (
    ENGAGEMENT_ID,
    LOCKED_VERSION_ID,
    OPEN_VERSION_ID,
    OTHER_ENGAGEMENT_ID,
    OTHER_VERSION_ID,
)
from tests.test_api_misstatements import linked_engagement, raise_one


def body(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "om": "400000.00",
        "pm": "250000.00",
        "ctt_fraction": "0.05",
        "basis": "5% of profit before tax per C-1; PM at 62.5% of OM; CTT declared at 5% of PM",
    }
    values.update(overrides)
    return values


def set_thresholds(api: TestClient, engagement_id: str, **overrides: Any) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/thresholds", json=body(**overrides))


def test_setting_thresholds_records_the_three_lines_the_fraction_and_who(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    answer = set_thresholds(api, engagement_id)
    assert answer.status_code == 201, answer.text
    threshold = answer.json()
    assert threshold["om"] == "400000.00"
    assert threshold["pm"] == "250000.00"
    assert threshold["ctt"] == "12500.00"
    assert threshold["ctt_fraction"] == "0.05"
    assert threshold["basis"].startswith("5% of profit before tax")
    assert threshold["set_by"] == "senior@firm"
    assert threshold["is_current"] is True
    assert threshold["superseded_by"] is None
    assert threshold["recompute_event"] is None  # the first version supersedes nothing
    assert threshold["version_no"] == 1
    assert threshold["spine"] == {
        "version_id": str(OPEN_VERSION_ID),
        "pm_at_set": "250000.00",
        "pm_status_at_set": "available",
    }
    assert threshold["spine_pm_check"]["status"] == "match"
    assert threshold["spine_pm_check"]["recorded_version_id"] == str(OPEN_VERSION_ID)
    assert threshold["spine_pm_check"]["pinned_version_id"] == str(OPEN_VERSION_ID)
    assert threshold["authorisation"]["enforced"] is False
    assert "B9" in threshold["authorisation"]["policy"]
    assert (
        api.get(f"/api/engagements/{engagement_id}").json()["current_threshold_id"]
        == threshold["id"]
    )


def test_validation_no_default_fraction_and_the_spec_s_own_ordering(api: TestClient) -> None:
    engagement_id = api.post("/api/engagements", json={"label": "FY26"}).json()["id"]
    missing = set_thresholds(api, engagement_id, ctt_fraction=None)
    assert missing.status_code == 422
    for fraction in ("0", "1", "1.5", "-0.1"):
        assert set_thresholds(api, engagement_id, ctt_fraction=fraction).status_code == 422, (
            fraction
        )
    assert set_thresholds(api, engagement_id, om="0").status_code == 422
    assert set_thresholds(api, engagement_id, pm="-5").status_code == 422
    assert set_thresholds(api, engagement_id, basis="  ").status_code == 422
    assert set_thresholds(api, engagement_id, pm="1.005").status_code == 422
    tiny = set_thresholds(api, engagement_id, pm="0.01", ctt_fraction="0.1")
    assert tiny.status_code == 422
    assert "rounds to nothing" in tiny.text
    assert api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"] is None


def test_ctt_is_rounded_to_the_paisa_and_the_fraction_kept_exactly(api: TestClient) -> None:
    engagement_id = api.post("/api/engagements", json={"label": "FY26"}).json()["id"]
    answer = set_thresholds(api, engagement_id, pm="333333.33", ctt_fraction="0.05")
    assert answer.status_code == 201
    assert answer.json()["ctt"] == "16666.67"  # 16666.6665 half up (D27)
    assert answer.json()["ctt_fraction"] == "0.05"


# ---- B13 (D34): performance materiality must be below overall materiality -----------------


def test_pm_below_om_is_accepted_and_reported_as_enforced(api: TestClient) -> None:
    engagement_id = api.post("/api/engagements", json={"label": "FY26"}).json()["id"]
    answer = set_thresholds(api, engagement_id, om="400000.00", pm="399999.99")
    assert answer.status_code == 201, answer.text
    assert answer.json()["checks"]["pm_below_om"] is True
    assert "enforced" in answer.json()["checks"]["note"]
    assert "ck_threshold_pm_below_om" in answer.json()["checks"]["note"]


@pytest.mark.parametrize(
    ("om", "pm"),
    [("250000.00", "250000.00"), ("100000.00", "250000.00"), ("1.00", "2.00")],
)
def test_pm_equal_to_or_above_om_is_refused_before_anything_is_written(
    api: TestClient, om: str, pm: str
) -> None:
    engagement_id = api.post("/api/engagements", json={"label": "FY26"}).json()["id"]
    refused = set_thresholds(api, engagement_id, om=om, pm=pm, ctt_fraction="0.05")
    assert refused.status_code == 422
    detail = refused.text
    assert "performance materiality" in detail and "must be below overall materiality" in detail
    assert "SA 320 paragraph 9" in detail
    assert api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"] is None
    assert api.get(f"/api/engagements/{engagement_id}/thresholds/history").json() == []
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == []


def test_a_revision_with_pm_at_or_above_om_leaves_the_history_and_the_trail_untouched(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    first = set_thresholds(api, engagement_id).json()
    second = set_thresholds(api, engagement_id, pm="240000.00").json()
    history_before = api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
    events_before = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [v["id"] for v in history_before] == [second["id"], first["id"]]
    assert len(events_before) == 1
    for om, pm in (("300000.00", "300000.00"), ("300000.00", "350000.00")):
        refused = set_thresholds(api, engagement_id, om=om, pm=pm)
        assert refused.status_code == 422, (om, pm)
    assert api.get(f"/api/engagements/{engagement_id}/thresholds/history").json() == history_before
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == events_before
    current = api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"]
    assert current["id"] == second["id"] and current["version_no"] == 2
    # A valid revision still works afterwards and gets version 3, not 4 or 5.
    third = set_thresholds(api, engagement_id, om="300000.00", pm="200000.00").json()
    assert third["version_no"] == 3


def test_a_revision_supersedes_once_and_records_the_recompute(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    first = set_thresholds(api, engagement_id).json()
    second = set_thresholds(api, engagement_id, pm="200000.00", ctt_fraction="0.04").json()
    assert second["is_current"] is True
    assert second["ctt"] == "8000.00"
    event = second["recompute_event"]
    assert event["kind"] == "threshold_recompute"
    assert event["actor"] == "senior@firm"
    assert event["payload"]["previous_threshold_id"] == first["id"]
    assert event["payload"]["current_threshold_id"] == second["id"]
    assert event["payload"]["changes"] == {
        "pm": {"from": "250000.00", "to": "200000.00"},
        "ctt": {"from": "12500.00", "to": "8000.00"},
        "ctt_fraction": {"from": "0.05", "to": "0.04"},
    }
    assert "recomputes on read" in event["payload"]["bands"]
    versions = api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
    assert [v["id"] for v in versions] == [second["id"], first["id"]]
    assert versions[1]["superseded_by"] == second["id"]
    assert versions[1]["is_current"] is False
    current = api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"]
    assert current["id"] == second["id"]
    trail = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [entry["kind"] for entry in trail] == ["threshold_recompute"]
    assert trail[0]["id"] == event["id"]
    third = set_thresholds(api, engagement_id, pm="200000.00", ctt_fraction="0.04").json()
    assert third["recompute_event"]["payload"]["changes"] == {}  # same figures: still a version
    assert len(api.get(f"/api/engagements/{engagement_id}/events").json()) == 2


def test_the_spine_pm_check_reports_match_mismatch_and_the_reasons_it_cannot_check(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    path = f"/api/engagements/{engagement_id}/thresholds"
    assert set_thresholds(api, engagement_id).json()["spine_pm_check"]["status"] == "match"
    mismatch = set_thresholds(api, engagement_id, pm="240000.00").json()["spine_pm_check"]
    assert mismatch["status"] == "mismatch"
    assert mismatch == {
        "status": "mismatch",
        "our_pm": "240000.00",
        "spine_pm": "250000.00",
        "recorded_version_id": str(OPEN_VERSION_ID),
        "pinned_version_id": str(OPEN_VERSION_ID),
        "detail": mismatch["detail"],
    }
    assert "240000.00" in mismatch["detail"] and "B4" in mismatch["detail"]
    spine.versions[OPEN_VERSION_ID].performance_materiality = None
    assert api.get(path).json()["current"]["spine_pm_check"]["status"] == "spine_has_no_pm"
    spine.unreachable = True
    check = api.get(path).json()["current"]["spine_pm_check"]
    assert check["status"] == "unreachable"
    assert check["spine_pm"] is None
    spine.unreachable = False
    api.app.state.spine_client = None  # type: ignore[attr-defined]
    assert api.get(path).json()["current"]["spine_pm_check"]["status"] == "not_configured"
    unpinned = api.post("/api/engagements", json={"label": "no version"}).json()["id"]
    answer = set_thresholds(api, unpinned).json()
    assert answer["spine"] == {
        "version_id": None,
        "pm_at_set": None,
        "pm_status_at_set": "not_pinned",
    }
    assert answer["spine_pm_check"]["status"] == "not_pinned"


def test_thresholds_set_on_another_spine_version_record_that_version(api: TestClient) -> None:
    use_spine(api)
    created = api.post(
        "/api/engagements",
        json={
            "label": "other",
            "spine_engagement_id": str(OTHER_ENGAGEMENT_ID),
            "spine_version_id": str(OTHER_VERSION_ID),
        },
    ).json()
    answer = set_thresholds(api, created["id"]).json()
    assert answer["spine"]["version_id"] == str(OTHER_VERSION_ID)
    assert answer["spine"]["pm_at_set"] is None  # that version carries no PM
    assert answer["spine"]["pm_status_at_set"] == "not_set"
    assert answer["spine_pm_check"]["status"] == "spine_has_no_pm"


# ---- D-6: the reading at set time is never an ambiguous null -----------------------------


def test_the_spine_pm_status_at_set_names_each_situation(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    spine.unreachable = True
    unreachable = set_thresholds(api, engagement_id).json()["spine"]
    assert unreachable == {
        "version_id": str(OPEN_VERSION_ID),
        "pm_at_set": None,
        "pm_status_at_set": "unreachable",
    }
    spine.unreachable = False
    api.app.state.spine_client = None  # type: ignore[attr-defined]
    not_configured = set_thresholds(api, engagement_id).json()["spine"]
    assert not_configured["pm_status_at_set"] == "not_configured"
    assert not_configured["pm_at_set"] is None
    use_spine(api)
    available = set_thresholds(api, engagement_id).json()["spine"]
    assert available == {
        "version_id": str(OPEN_VERSION_ID),
        "pm_at_set": "250000.00",
        "pm_status_at_set": "available",
    }
    statuses = [
        v["spine"]["pm_status_at_set"]
        for v in api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
    ]
    assert statuses == ["available", "not_configured", "unreachable"]


# ---- D-7: the check is against the recorded version, never silently another --------------


def test_a_changed_pin_is_reported_not_compared_across(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    first = set_thresholds(api, engagement_id).json()
    assert first["spine_pm_check"]["status"] == "match"
    relinked = api.post(
        f"/api/engagements/{engagement_id}/spine-link",
        json={
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(LOCKED_VERSION_ID),
        },
    )
    assert relinked.status_code == 200
    check = api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"][
        "spine_pm_check"
    ]
    assert check["status"] == "pinned_version_changed"
    assert check["recorded_version_id"] == str(OPEN_VERSION_ID)
    assert check["pinned_version_id"] == str(LOCKED_VERSION_ID)
    assert check["spine_pm"] is None
    assert str(OPEN_VERSION_ID) in check["detail"] and str(LOCKED_VERSION_ID) in check["detail"]
    # A version set against the new pin compares against that pin.
    again = set_thresholds(api, engagement_id).json()
    assert again["spine"]["version_id"] == str(LOCKED_VERSION_ID)
    assert again["spine_pm_check"]["status"] == "match"


def test_a_pin_set_or_cleared_after_the_threshold_is_a_changed_pin_too(api: TestClient) -> None:
    use_spine(api)
    unpinned = api.post("/api/engagements", json={"label": "pinned later"}).json()["id"]
    first = set_thresholds(api, unpinned).json()
    assert first["spine_pm_check"]["status"] == "not_pinned"
    linked = api.post(
        f"/api/engagements/{unpinned}/spine-link",
        json={
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    )
    assert linked.status_code == 200, linked.text
    check = api.get(f"/api/engagements/{unpinned}/thresholds").json()["current"]["spine_pm_check"]
    assert check["status"] == "pinned_version_changed"
    assert check["recorded_version_id"] is None
    assert check["pinned_version_id"] == str(OPEN_VERSION_ID)
    assert "no Spine version was pinned" in check["detail"]
    # Set against the pin, then clear the pin: the other direction.
    second = set_thresholds(api, unpinned).json()
    assert second["spine_pm_check"]["status"] == "match"
    cleared = api.post(f"/api/engagements/{unpinned}/spine-link", json={})
    assert cleared.status_code == 200, cleared.text
    check = api.get(f"/api/thresholds/{second['id']}").json()["spine_pm_check"]
    assert check["status"] == "pinned_version_changed"
    assert check["recorded_version_id"] == str(OPEN_VERSION_ID)
    assert check["pinned_version_id"] is None
    assert "now has no pinned version" in check["detail"]


# ---- D-8: history is ordered by version number, never by the clock ------------------------


def test_history_is_in_version_order_however_fast_versions_are_set(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    ids = [set_thresholds(api, engagement_id, pm=str(250000 - n)).json()["id"] for n in range(6)]
    versions = api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
    assert [v["version_no"] for v in versions] == [6, 5, 4, 3, 2, 1]
    assert [v["id"] for v in versions] == list(reversed(ids))
    assert [v["superseded_by"] for v in versions] == [None, *reversed(ids[1:])]
    assert (
        api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"]["id"] == ids[-1]
    )
    event = api.get(f"/api/engagements/{engagement_id}/events").json()[-1]["payload"]
    assert (event["previous_version_no"], event["current_version_no"]) == (5, 6)


# ---- D-9: superseding never touches the historical row's figures ---------------------------


def test_superseding_leaves_the_old_version_exactly_as_set(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    first = set_thresholds(api, engagement_id).json()
    set_thresholds(
        api, engagement_id, om="500000.00", pm="300000.00", ctt_fraction="0.03", basis="revised"
    )
    old = next(
        v
        for v in api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
        if v["id"] == first["id"]
    )
    frozen = ("version_no", "om", "pm", "ctt", "ctt_fraction", "basis", "set_by", "set_at", "spine")
    assert {key: old[key] for key in frozen} == {key: first[key] for key in frozen}
    assert old["superseded_by"] is not None
    assert old["is_current"] is False


def test_acceptance_2_changing_materiality_recomputes_every_band_and_records_it(
    api: TestClient,
) -> None:
    """Spec acceptance 2: a band is never stored, so revising the thresholds changes every
    band on the next read, and the revision writes the recompute event (D26, D33)."""
    use_spine(api)
    engagement_id = linked_engagement(api)
    raised = raise_one(api, engagement_id).json()  # profit and net assets effects of 10,000
    assert raised["band"] is None
    assert "no thresholds have been set" in raised["band_basis"]
    assert raised["banding"]["threshold_id"] is None

    first = set_thresholds(api, engagement_id).json()  # PM 250,000, CTT 12,500
    read = api.get(f"/api/misstatements/{raised['id']}").json()
    assert read["band"] == "clearly_trivial"  # 10,000 is below CTT
    assert read["banding"]["bands"] == {
        "profit": "clearly_trivial",
        "net_assets": "clearly_trivial",
    }
    assert read["banding"]["amounts"] == {"profit": "10000.00", "net_assets": "10000.00"}
    assert read["banding"]["threshold_id"] == first["id"]
    assert read["banding"]["threshold_version_no"] == 1

    second = set_thresholds(api, engagement_id, ctt_fraction="0.02").json()  # CTT 5,000
    read = api.get(f"/api/misstatements/{raised['id']}").json()
    assert read["band"] == "accumulated"
    assert read["banding"]["threshold_id"] == second["id"]
    assert read["banding"]["threshold_version_no"] == 2

    third = set_thresholds(
        api, engagement_id, om="400000.00", pm="9000.00", ctt_fraction="0.5"
    ).json()
    listed = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]
    assert listed["band"] == "individually_significant"  # 10,000 is above a PM of 9,000
    assert listed["banding"]["threshold_id"] == third["id"]

    events = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [event["kind"] for event in events] == ["threshold_recompute", "threshold_recompute"]
    assert events[-1]["payload"]["current_threshold_id"] == third["id"]


def test_thresholds_need_an_identity_and_an_engagement(api: TestClient) -> None:
    assert set_thresholds(api, str(uuid.uuid4())).status_code == 404
    engagement_id = api.post("/api/engagements", json={"label": "FY26"}).json()["id"]
    act_as(api, None)
    assert set_thresholds(api, engagement_id).status_code == 503
    assert api.get(f"/api/engagements/{engagement_id}/thresholds").status_code == 200


# ---- D35: a version by id, and the Spine read kept outside the engagement lock ------------


def test_a_threshold_version_can_be_read_by_its_id_current_or_superseded(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    first = set_thresholds(api, engagement_id).json()
    second = set_thresholds(api, engagement_id, pm="240000.00").json()
    current = api.get(f"/api/thresholds/{second['id']}")
    assert current.status_code == 200
    assert current.json()["id"] == second["id"]
    assert current.json()["version_no"] == 2
    assert current.json()["is_current"] is True
    assert current.json()["spine_pm_check"]["status"] == "mismatch"  # 240,000 against 250,000
    old = api.get(f"/api/thresholds/{first['id']}")
    assert old.status_code == 200
    assert old.json()["version_no"] == 1
    assert old.json()["is_current"] is False
    assert old.json()["superseded_by"] == second["id"]
    assert old.json()["pm"] == "250000.00"
    assert old.json()["spine_pm_check"]["status"] == "match"
    assert old.json()["authorisation"]["enforced"] is False


def test_an_unknown_threshold_id_is_404(api: TestClient) -> None:
    missing = api.get(f"/api/thresholds/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert "no threshold version" in missing.json()["detail"]


def test_reading_by_id_checks_against_the_versions_own_recorded_spine_version(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    old = set_thresholds(api, engagement_id).json()  # recorded against the open version
    relinked = api.post(
        f"/api/engagements/{engagement_id}/spine-link",
        json={
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(LOCKED_VERSION_ID),
        },
    )
    assert relinked.status_code == 200
    new = set_thresholds(api, engagement_id).json()  # recorded against the locked version
    old_read = api.get(f"/api/thresholds/{old['id']}").json()
    assert old_read["spine"]["version_id"] == str(OPEN_VERSION_ID)
    assert old_read["spine_pm_check"]["status"] == "pinned_version_changed"
    assert old_read["spine_pm_check"]["recorded_version_id"] == str(OPEN_VERSION_ID)
    assert old_read["spine_pm_check"]["pinned_version_id"] == str(LOCKED_VERSION_ID)
    new_read = api.get(f"/api/thresholds/{new['id']}").json()
    assert new_read["spine"]["version_id"] == str(LOCKED_VERSION_ID)
    assert new_read["spine_pm_check"]["status"] == "match"


def test_a_pin_change_between_the_spine_read_and_the_lock_records_the_locked_pin(
    api: TestClient,
) -> None:
    """The Spine is read before the engagement row is locked (D35). If another request
    re-pins the engagement in between, the pin is seen under the lock and the Spine is read
    again, so the recorded version and its PM always belong together."""
    from decimal import Decimal
    from typing import ClassVar, cast

    from sqlalchemy import update

    from oak_misstatements.models import Engagement
    from oak_misstatements.schemas.thresholds import ThresholdIn
    from oak_misstatements.services.spine_client import SpineClient, SpineVersion
    from oak_misstatements.services.thresholds import set_threshold

    spine = use_spine(api)
    spine.versions[LOCKED_VERSION_ID].performance_materiality = "260000.00"
    engagement_id = linked_engagement(api)  # pinned to the open version, PM 250,000
    real = spine.client()
    factory = api.app.state.session_factory  # type: ignore[attr-defined]
    body = ThresholdIn(
        om=Decimal("400000"), pm=Decimal("250000"), ctt_fraction=Decimal("0.05"), basis="C-1"
    )

    class PinFlipper:
        """Answers like the Spine, but the first version read re-pins the engagement in
        the database, as a concurrent request would, before the lock is taken."""

        calls: ClassVar[list[uuid.UUID]] = []

        def __init__(self, session: Any, engagement: Any) -> None:
            self.session = session
            self.engagement_id = engagement.id

        def version(self, version_id: uuid.UUID) -> SpineVersion:
            PinFlipper.calls.append(version_id)
            if len(PinFlipper.calls) == 1:
                self.session.execute(
                    update(Engagement)
                    .where(Engagement.id == self.engagement_id)
                    .values(spine_version_id=LOCKED_VERSION_ID)
                )
                self.session.flush()
            return real.version(version_id)

    with factory.begin() as session:
        engagement = session.get(Engagement, uuid.UUID(engagement_id))
        assert engagement is not None
        threshold, _event = set_threshold(
            session,
            cast(SpineClient, PinFlipper(session, engagement)),
            engagement,
            body,
            set_by="t",
        )
        assert PinFlipper.calls == [OPEN_VERSION_ID, LOCKED_VERSION_ID]
        assert threshold.spine_version_id == LOCKED_VERSION_ID
        assert threshold.spine_pm_at_set == Decimal("260000.00")
        assert threshold.spine_pm_status_at_set == "available"
        threshold_id = threshold.id
    read = api.get(f"/api/thresholds/{threshold_id}").json()
    assert read["spine"] == {
        "version_id": str(LOCKED_VERSION_ID),
        "pm_at_set": "260000.00",
        "pm_status_at_set": "available",
    }
    # The recorded version is the locked one, whose PM is 260,000 against our 250,000.
    assert read["spine_pm_check"]["status"] == "mismatch"
    assert read["spine_pm_check"]["recorded_version_id"] == str(LOCKED_VERSION_ID)
    assert read["spine_pm_check"]["spine_pm"] == "260000.00"


def test_without_a_pin_change_the_spine_is_read_once_before_the_lock(api: TestClient) -> None:
    from decimal import Decimal
    from typing import cast

    from oak_misstatements.models import Engagement
    from oak_misstatements.schemas.thresholds import ThresholdIn
    from oak_misstatements.services.spine_client import SpineClient, SpineVersion
    from oak_misstatements.services.thresholds import set_threshold

    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    real = spine.client()
    reads: list[uuid.UUID] = []

    class Counting:
        def version(self, version_id: uuid.UUID) -> SpineVersion:
            reads.append(version_id)
            return real.version(version_id)

    factory = api.app.state.session_factory  # type: ignore[attr-defined]
    body = ThresholdIn(
        om=Decimal("400000"), pm=Decimal("250000"), ctt_fraction=Decimal("0.05"), basis="C-1"
    )
    with factory.begin() as session:
        engagement = session.get(Engagement, uuid.UUID(engagement_id))
        assert engagement is not None
        threshold, _event = set_threshold(
            session, cast(SpineClient, Counting()), engagement, body, set_by="t"
        )
        assert reads == [OPEN_VERSION_ID]
        assert threshold.spine_version_id == OPEN_VERSION_ID
        assert threshold.spine_pm_at_set == Decimal("250000.00")
