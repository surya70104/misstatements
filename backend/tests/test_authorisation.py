"""B9 (architecture D36): what the module enforces about who acts, and what it declares it
does not. Identity is required on every write, taken from the request's identity source and
never from its body, recorded on the row, and the record cannot be rewritten. No role or
permission is enforced, and every answer says so."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oak_misstatements.config import Settings
from oak_misstatements.services.authorisation import authorisation_json, production_grade
from tests.conftest import APP_URL, act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, OPEN_VERSION_ID

THRESHOLDS = {"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"}
LINES = [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}]
MISSTATEMENT = {
    "type": "factual",
    "description": "Rent not accrued",
    "raised_from": "wp",
    "source_ref": "E-4.2",
    "lines": LINES,
}


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


# ---- missing identity: every write refuses, nothing is written ------------------------------


def test_every_write_needs_an_identity_and_every_read_does_not(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    act_as(api, None)
    refusals = [
        api.post("/api/engagements", json={"label": "x"}),
        api.post(
            f"/api/engagements/{engagement_id}/spine-link",
            json={"spine_engagement_id": str(ENGAGEMENT_ID)},
        ),
        api.post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS),
        api.post(f"/api/engagements/{engagement_id}/misstatements", json=MISSTATEMENT),
    ]
    for refused in refusals:
        assert refused.status_code == 503, refused.text
        assert "No identity is configured" in refused.json()["detail"]
    assert api.get("/api/engagements").status_code == 200
    assert len(api.get("/api/engagements").json()) == 1
    assert api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"] is None
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []
    assert api.get(f"/api/engagements/{engagement_id}/events").json() == []


# ---- valid identity: recorded on the row it creates, from the request, never the body ------


def test_the_acting_identity_is_recorded_on_everything_it_creates(api: TestClient) -> None:
    use_spine(api)
    act_as(api, "manager@firm")
    engagement_id = linked(api)
    assert api.get(f"/api/engagements/{engagement_id}").json()["created_by"] == "manager@firm"
    act_as(api, "partner@firm")
    first = api.post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS).json()
    assert first["set_by"] == "partner@firm"
    act_as(api, "senior@firm")
    second = api.post(
        f"/api/engagements/{engagement_id}/thresholds", json={**THRESHOLDS, "pm": "240000.00"}
    ).json()
    assert second["set_by"] == "senior@firm"
    assert second["recompute_event"]["actor"] == "senior@firm"
    raised = api.post(f"/api/engagements/{engagement_id}/misstatements", json=MISSTATEMENT).json()
    assert raised["created_by"] == "senior@firm"
    assert raised["current"]["raised_by"] == "senior@firm"
    # The earlier rows keep their own actors.
    history = api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
    assert [v["set_by"] for v in history] == ["senior@firm", "partner@firm"]


def test_an_actor_in_the_request_body_is_refused_not_ignored(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    cases = [
        ("/api/engagements", {"label": "x", "created_by": "forged@firm"}),
        (
            f"/api/engagements/{engagement_id}/spine-link",
            {"spine_engagement_id": str(ENGAGEMENT_ID), "set_by": "forged@firm"},
        ),
        (f"/api/engagements/{engagement_id}/thresholds", {**THRESHOLDS, "set_by": "forged@firm"}),
        (
            f"/api/engagements/{engagement_id}/misstatements",
            {**MISSTATEMENT, "raised_by": "forged@firm"},
        ),
        (
            f"/api/engagements/{engagement_id}/misstatements",
            {**MISSTATEMENT, "lines": [{**LINES[0], "posted_by": "x"}, LINES[1]]},
        ),
    ]
    for path, body in cases:
        refused = api.post(path, json=body)
        assert refused.status_code == 422, (path, refused.text)
        assert "Extra inputs are not permitted" in refused.text, path
    assert api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"] is None
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []


# ---- header mode: the proxy's identity, exactly once, plausible -----------------------------


def header_mode(api: TestClient) -> None:
    settings = cast(FastAPI, api.app).state.settings
    settings.auth = "header"
    settings.dev_user = None


def test_header_mode_records_the_proxys_identity_and_refuses_the_rest(api: TestClient) -> None:
    use_spine(api)
    header_mode(api)
    missing = api.post("/api/engagements", json={"label": "x"})
    assert missing.status_code == 401
    assert "did not present X-Authenticated-User" in missing.json()["detail"]
    blank = api.post(
        "/api/engagements", json={"label": "x"}, headers={"X-Authenticated-User": "  "}
    )
    assert blank.status_code == 401
    twice = api.post(
        "/api/engagements",
        json={"label": "x"},
        headers=[("X-Authenticated-User", "a@firm"), ("X-Authenticated-User", "b@firm")],
    )
    assert twice.status_code == 401
    assert "presented 2 times" in twice.json()["detail"]
    created = api.post(
        "/api/engagements", json={"label": "x"}, headers={"X-Authenticated-User": "partner@firm"}
    )
    assert created.status_code == 201, created.text
    assert created.json()["created_by"] == "partner@firm"
    assert created.json()["authorisation"]["identity_mode"] == "header"
    assert api.get("/api/engagements").status_code == 200  # reads need no header


# ---- the notice: never a claim of enforcement -----------------------------------------------


def test_every_answer_declares_that_no_authorisation_is_enforced(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    threshold = api.post(f"/api/engagements/{engagement_id}/thresholds", json=THRESHOLDS).json()
    raised = api.post(f"/api/engagements/{engagement_id}/misstatements", json=MISSTATEMENT).json()
    answers: list[dict[str, Any]] = [
        api.get(f"/api/engagements/{engagement_id}").json(),
        api.get("/api/engagements").json()[0],
        threshold,
        api.get(f"/api/engagements/{engagement_id}/thresholds").json()["current"],
        api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()[0],
        api.get(f"/api/thresholds/{threshold['id']}").json(),
        raised,
        api.get(f"/api/misstatements/{raised['id']}").json(),
        api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0],
    ]
    for answer in answers:
        notice = answer["authorisation"]
        assert notice["enforced"] is False
        assert "B9" in notice["policy"]
        assert notice["identity_mode"] == "dev"
        assert notice["production_grade"] is False
        assert "role claim" in notice["missing"] and "partner" in notice["missing"]
        assert notice["partner_actions"]["enforced"] is True
        assert notice["partner_actions"]["available"] is False
        assert notice["partner_actions"]["actions"] == ["soft_gate_acknowledgement", "conclusion"]
        assert "fails closed" in notice["partner_actions"]["detail"]


def test_only_a_proxy_identity_in_production_is_production_grade(
    make_settings: Callable[..., Settings],
) -> None:
    development = make_settings(database_url=APP_URL, dev_user="dev@localhost")
    assert production_grade(development) is False
    assert authorisation_json(development)["identity_mode"] == "dev"
    header_in_test = make_settings(database_url=APP_URL, auth="header", trusted_proxies="10.0.0.5")
    assert production_grade(header_in_test) is False
    production = make_settings(
        env="production", auth="header", trusted_proxies="10.0.0.5", database_url=APP_URL
    )
    assert production_grade(production) is True
    assert authorisation_json(production)["enforced"] is False  # still no role check
