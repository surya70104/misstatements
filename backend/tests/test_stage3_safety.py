"""Two safety points of Stage 3 (D42).

1. History cannot be altered: the application refuses to update or delete an append-only
   row before the database is asked (the database's own triggers and grants are proven from
   the rendered migrations in ``test_migration_sql.py`` and, once a test database exists,
   by ``test_db_rules.py``).
2. A move whose local commit fails after the Financial Spine decided is reported as a
   failure, never as success, and repeating it records the Spine's existing decision
   without a second adjustment or a second decision. Stale readers cannot create a
   duplicate version or a second posting.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, update
from sqlalchemy.exc import OperationalError

from oak_misstatements.models import (
    Engagement,
    Event,
    Misstatement,
    MisstatementLineClass,
    MisstatementVersion,
    Threshold,
)
from oak_misstatements.models.guard import APPEND_ONLY_TABLES, AppendOnlyViolation
from oak_misstatements.services.misstatements import get_misstatement
from tests.conftest import use_spine
from tests.fake_spine import OPEN_VERSION_ID, FakeSpine
from tests.test_api_transitions import (
    PROVISION_BEFORE,
    RENT_BEFORE,
    adjustment_of,
    balances,
    communicated,
    decisions,
    linked,
    move,
    raise_one,
    read,
)

THRESHOLDS = {"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"}


def fail_next_commit(api: TestClient) -> None:
    """Make the next commit of the running app fail, once, as a lost connection would."""
    factory = cast(FastAPI, api.app).state.session_factory
    state = {"armed": True}

    def boom(_session: Any) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OperationalError("COMMIT", {}, Exception("connection lost at commit"))

    event.listen(factory, "before_commit", boom)


def quiet(api: TestClient) -> TestClient:
    return TestClient(api.app, raise_server_exceptions=False)


# ---- 1. history cannot be altered by the application ---------------------------------------


def test_the_guard_covers_every_append_only_table() -> None:
    assert {
        "misstatement",
        "misstatement_version",
        "misstatement_line_class",
        "event",
        "evaluation",
    } == APPEND_ONLY_TABLES


def test_the_application_cannot_update_or_delete_an_earlier_version(api: TestClient) -> None:
    _spine, engagement_id, record = communicated(api)
    api.post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS)
    api.post(f"/api/engagements/{engagement_id}/thresholds", json={**THRESHOLDS, "basis": "C-2"})
    before = read(api, record["id"])["versions"]
    factory = cast(FastAPI, api.app).state.session_factory
    for model in (Misstatement, MisstatementVersion, MisstatementLineClass, Event):
        with factory() as session:
            row = session.scalars(select(model)).first()
            assert row is not None, model.__name__
            session.delete(row)
            with pytest.raises(AppendOnlyViolation, match="never deleted"):
                session.flush()
    for model, field in (
        (Misstatement, "created_by"),
        (MisstatementVersion, "state"),
        (MisstatementVersion, "description"),
        (MisstatementVersion, "refusal_reason"),
        (MisstatementLineClass, "section"),
        (Event, "actor"),
    ):
        with factory() as session:
            row = session.scalars(select(model)).first()
            setattr(row, field, "tampered")
            with pytest.raises(AppendOnlyViolation, match="never an update"):
                session.flush()
            with pytest.raises(AppendOnlyViolation):
                session.commit()
    for model in (Misstatement, MisstatementVersion, MisstatementLineClass, Event):
        with factory() as session:
            with pytest.raises(AppendOnlyViolation, match="UPDATE is not allowed"):
                session.execute(update(model).values(created_at=func.now()))
            with pytest.raises(AppendOnlyViolation, match="DELETE is not allowed"):
                session.execute(delete(model))
    assert read(api, record["id"])["versions"] == before
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MisstatementVersion)) == 2
        assert session.scalar(select(func.count()).select_from(Event)) == 1


def test_the_guard_leaves_the_two_permitted_updates_alone(api: TestClient) -> None:
    """A threshold is superseded once and an engagement's Spine link may change; each is
    held by its own database trigger, not by this guard."""
    use_spine(api)
    engagement_id = linked(api)
    first = api.post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS).json()
    second = api.post(
        f"/api/engagements/{engagement_id}/thresholds", json={**THRESHOLDS, "basis": "C-2"}
    ).json()
    assert second["version_no"] == 2
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        old = session.get(Threshold, uuid.UUID(first["id"]))
        assert old is not None and old.superseded_by == uuid.UUID(second["id"])
        engagement = session.get(Engagement, uuid.UUID(engagement_id))
        assert engagement is not None
    cleared = api.post(f"/api/engagements/{engagement_id}/spine-link", json={})
    assert cleared.status_code == 200


def test_a_move_never_touches_the_version_it_moves_from(api: TestClient) -> None:
    _spine, _engagement, record = communicated(api)
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        rows = session.execute(
            select(MisstatementVersion.id, MisstatementVersion.created_at).order_by(
                MisstatementVersion.version_no
            )
        ).all()
    assert move(api, record["id"], "refused", "management disagrees").status_code == 201
    with factory() as session:
        after = session.execute(
            select(MisstatementVersion.id, MisstatementVersion.created_at).order_by(
                MisstatementVersion.version_no
            )
        ).all()
    assert after[:2] == rows  # the same two rows, same ids, same timestamps
    assert len(after) == 3


# ---- 2. the Spine decided, the local commit failed -----------------------------------------


@pytest.mark.parametrize(
    ("to", "reason", "spine_status"),
    [
        ("corrected", None, "accepted"),
        ("refused", "management disagrees", "refused"),
        ("withdrawn", "raised in error", "refused"),
    ],
)
def test_a_failed_commit_after_the_spine_decided_is_a_failure_and_a_retry_completes_it(
    api: TestClient, to: str, reason: str | None, spine_status: str
) -> None:
    spine, engagement_id, record = communicated(api)
    api.post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS)
    fail_next_commit(api)
    body: dict[str, Any] = {"to": to} if reason is None else {"to": to, "reason": reason}
    failed = quiet(api).post(f"/api/misstatements/{record['id']}/transitions", json=body)
    # Never a success: the client is told nothing was recorded, and why.
    assert failed.status_code == 503
    assert "refused the commit" in failed.json()["detail"]
    assert "connection lost at commit" in failed.json()["detail"]
    assert "state_consistency" in failed.json()["detail"]
    # The Spine decided once; nothing was recorded here.
    adjustment = adjustment_of(spine, record)
    assert adjustment.status == spine_status
    first_note = adjustment.decision_note
    assert len(decisions(spine)) == 1
    seen = read(api, record["id"])
    assert [v["state"] for v in seen["versions"]] == ["raised", "communicated"]
    assert seen["state_consistency"]["consistent"] is False
    assert seen["state_consistency"]["adjustment_status"] == spine_status
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["state_consistency"]["inconsistent"] == ["M-1"]
    assert evaluation["sign_off"]["blocked"] is True
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:  # the rolled-back version left no snapshot rows behind
        assert session.scalar(select(func.count()).select_from(MisstatementLineClass)) == 4
    # The retry records the decision the Spine already holds.
    retried = move(api, record["id"], to, reason)
    assert retried.status_code == 201, retried.text
    done = retried.json()
    assert done["transition"]["decided_now"] is False
    assert done["transition"]["spine_decision"] == spine_status
    assert done["transition"]["note"] == first_note
    assert [v["state"] for v in done["versions"]] == ["raised", "communicated", to]
    assert done["state_consistency"]["consistent"] is True
    # No second decision, no second adjustment, and the posting happened exactly once.
    assert len(decisions(spine)) == 1
    assert len(spine.adjustments) == 1
    assert adjustment_of(spine, record).decision_note == first_note
    expected = (
        (RENT_BEFORE + Decimal("10000.00"), PROVISION_BEFORE - Decimal("10000.00"))
        if to == "corrected"
        else (RENT_BEFORE, PROVISION_BEFORE)
    )
    assert balances(spine) == expected
    after = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert after["state_consistency"]["inconsistent"] == []
    # A third attempt is an ordinary refusal: the state is final.
    assert move(api, record["id"], to, reason).status_code == 409
    assert len(decisions(spine)) == 1


def test_after_a_failed_commit_only_the_move_the_spine_holds_can_be_recorded(
    api: TestClient,
) -> None:
    spine, _engagement, record = communicated(api)
    fail_next_commit(api)
    assert (
        quiet(api)
        .post(f"/api/misstatements/{record['id']}/transitions", json={"to": "corrected"})
        .status_code
        == 503
    )
    for to in ("refused", "withdrawn"):
        refused = move(api, record["id"], to, "changed our mind")
        assert refused.status_code == 409, to
        assert "decides once" in refused.json()["detail"]
    assert len(read(api, record["id"])["versions"]) == 2
    assert len(decisions(spine)) == 1
    assert balances(spine) == (RENT_BEFORE + Decimal("10000.00"), Decimal("-90000.00"))


def test_a_failed_commit_is_never_reported_as_success_on_any_write(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    fail_next_commit(api)
    threshold = quiet(api).post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS)
    assert threshold.status_code == 503
    assert api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"] is None
    fail_next_commit(api)
    raised = quiet(api).post(
        f"/api/engagements/{engagement_id}/misstatements",
        json={
            "type": "factual",
            "description": "Rent",
            "raised_from": "wp",
            "source_ref": "E-1",
            "lines": [{"line_no": 5, "dr": "10.00"}, {"line_no": 3, "cr": "10.00"}],
        },
    )
    assert raised.status_code == 503
    assert "the Spine may already hold it" in raised.json()["detail"]
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []
    # The proposal the Spine took is an orphan a person must resolve (D22); it is proposed,
    # so it posts nothing.
    assert [a.status for a in spine.adjustments.values()] == ["proposed"]
    assert balances(spine) == (RENT_BEFORE, PROVISION_BEFORE)
    fail_next_commit(api)
    created = quiet(api).post("/api/engagements", json={"label": "lost"})
    assert created.status_code == 503
    assert [row["label"] for row in api.get("/api/engagements").json()] == ["FY26"]


# ---- 2b. two requests at once -----------------------------------------------------------------


def stale_reader(monkeypatch: pytest.MonkeyPatch, versions_seen: int) -> None:
    """Make the move read only the first ``versions_seen`` versions, as a request would
    that read before another request's move committed and was not held back by the lock."""

    def stale(session: Any, misstatement_id: uuid.UUID) -> Any:
        misstatement, versions = get_misstatement(session, misstatement_id)
        return misstatement, versions[:versions_seen]

    monkeypatch.setattr("oak_misstatements.services.transitions.get_misstatement", stale)


def test_a_second_request_that_read_stale_state_cannot_post_twice_or_fork_the_trail(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spine, _engagement, record = communicated(api)
    assert move(api, record["id"], "corrected").status_code == 201
    posted = balances(spine)
    stale_reader(monkeypatch, 2)  # the loser still believes the item is communicated
    same = quiet(api).post(
        f"/api/misstatements/{record['id']}/transitions", json={"to": "corrected"}
    )
    # The unique version number refuses the duplicate before the Spine is asked again.
    assert same.status_code == 503
    assert "Nothing was sent to the Financial Spine" in same.json()["detail"]
    other = quiet(api).post(
        f"/api/misstatements/{record['id']}/transitions",
        json={"to": "refused", "reason": "raced"},
    )
    assert other.status_code == 409  # the Spine holds accepted, and decides once
    monkeypatch.undo()
    assert [v["state"] for v in read(api, record["id"])["versions"]] == [
        "raised",
        "communicated",
        "corrected",
    ]
    assert len(decisions(spine)) == 1
    assert len(spine.adjustments) == 1
    assert balances(spine) == posted


def test_two_communications_at_once_leave_one_version(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    record = raise_one(api, engagement_id)
    assert move(api, record["id"], "communicated").status_code == 201
    stale_reader(monkeypatch, 1)  # the loser still believes the item is raised
    again = quiet(api).post(
        f"/api/misstatements/{record['id']}/transitions", json={"to": "communicated"}
    )
    assert again.status_code == 503
    monkeypatch.undo()
    assert [v["state"] for v in read(api, record["id"])["versions"]] == ["raised", "communicated"]
    assert decisions(spine) == []


def test_the_spine_itself_refuses_a_second_decision_whatever_this_module_does() -> None:
    double = FakeSpine()
    spine = double.client()
    adjustment = spine.propose(
        OPEN_VERSION_ID,
        kind="correction",
        narration="Rent",
        working_paper_ref="E-1",
        finding_ref="M-1",
        lines=[{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}],
    )
    spine.decide(OPEN_VERSION_ID, adjustment.adjustment_id, status="accepted", note=None)
    for status in ("accepted", "refused"):
        with pytest.raises(Exception, match="cannot be changed"):
            spine.decide(
                OPEN_VERSION_ID,
                adjustment.adjustment_id,
                status=cast(Any, status),
                note=None,
            )
    assert double.adjusted_balance(OPEN_VERSION_ID, "Rent") == Decimal("70000.00")
