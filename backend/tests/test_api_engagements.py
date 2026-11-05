"""Engagements and the Spine link over the API (D8). Runs on the in-memory stand-in when no
test database is configured (D24)."""

from __future__ import annotations

import uuid
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oak_misstatements.models import Engagement
from oak_misstatements.services.engagements import link_status
from oak_misstatements.services.spine_client import SpineClient
from tests.conftest import act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, LOCKED_VERSION_ID, OPEN_VERSION_ID, OTHER_VERSION_ID


def spine_answering(status: int, body: dict[str, object]) -> SpineClient:
    """A Spine that answers every call the same way."""
    return SpineClient(
        "http://spine.test",
        httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(status, json=body))),
    )


def test_an_engagement_needs_an_identity_and_a_label(api: TestClient) -> None:
    assert api.post("/api/engagements", json={"label": "  "}).status_code == 422
    act_as(api, None)
    refused = api.post("/api/engagements", json={"label": "FY26"})
    assert refused.status_code == 503
    assert "OAK_DEV_USER" in refused.json()["detail"]


def test_an_unlinked_engagement_is_created_and_listed(api: TestClient) -> None:
    created = api.post("/api/engagements", json={"label": "FY26 statutory"})
    assert created.status_code == 201
    body = created.json()
    assert body["label"] == "FY26 statutory"
    assert body["created_by"] == "senior@firm"
    assert body["spine"] == {
        "engagement_id": None,
        "version_id": None,
        "status": "unlinked",
        "is_locked": None,
        "detail": "no Financial Spine engagement is linked",
    }
    assert body["misstatements"] == 0
    listed = api.get("/api/engagements").json()
    assert [entry["id"] for entry in listed] == [body["id"]]
    assert api.get(f"/api/engagements/{body['id']}").json()["label"] == "FY26 statutory"
    assert api.get(f"/api/engagements/{uuid.uuid4()}").status_code == 404


def test_linking_without_a_spine_is_refused(api: TestClient) -> None:
    refused = api.post(
        "/api/engagements", json={"label": "FY26", "spine_engagement_id": str(ENGAGEMENT_ID)}
    )
    assert refused.status_code == 409
    assert "OAK_SPINE_URL" in refused.json()["detail"]


def test_a_link_is_verified_against_the_spine(api: TestClient) -> None:
    use_spine(api)
    created = api.post(
        "/api/engagements",
        json={
            "label": "FY26",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    )
    assert created.status_code == 201
    assert created.json()["spine"]["status"] == "verified"
    assert created.json()["spine"]["is_locked"] is False
    unknown = api.post(
        "/api/engagements", json={"label": "x", "spine_engagement_id": str(uuid.uuid4())}
    )
    assert unknown.status_code == 404
    wrong_owner = api.post(
        "/api/engagements",
        json={
            "label": "x",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OTHER_VERSION_ID),
        },
    )
    assert wrong_owner.status_code == 422
    assert "belongs to engagement" in wrong_owner.json()["detail"]
    orphan_version = api.post(
        "/api/engagements", json={"label": "x", "spine_version_id": str(OPEN_VERSION_ID)}
    )
    assert orphan_version.status_code == 422


def test_the_link_can_be_set_changed_and_cleared_while_nothing_is_raised(api: TestClient) -> None:
    use_spine(api)
    engagement_id = api.post("/api/engagements", json={"label": "FY26"}).json()["id"]
    path = f"/api/engagements/{engagement_id}/spine-link"
    linked = api.post(
        path,
        json={
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(LOCKED_VERSION_ID),
        },
    )
    assert linked.status_code == 200
    assert linked.json()["spine"]["is_locked"] is True
    changed = api.post(
        path,
        json={"spine_engagement_id": str(ENGAGEMENT_ID), "spine_version_id": str(OPEN_VERSION_ID)},
    )
    assert changed.json()["spine"]["version_id"] == str(OPEN_VERSION_ID)
    cleared = api.post(path, json={})
    assert cleared.json()["spine"]["status"] == "unlinked"


def test_the_detail_reports_a_spine_that_is_unreachable_or_has_lost_the_version(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = api.post(
        "/api/engagements",
        json={
            "label": "FY26",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    ).json()["id"]
    spine.unreachable = True
    assert api.get(f"/api/engagements/{engagement_id}").json()["spine"]["status"] == "unreachable"
    spine.unreachable = False
    del spine.versions[OPEN_VERSION_ID]
    missing = api.get(f"/api/engagements/{engagement_id}").json()["spine"]
    assert missing["status"] == "missing"
    assert "No spine_version" in missing["detail"]


# ---- D-2: a Spine error during a read is a status, never a leaked 409 or 422 -------------


def test_link_status_turns_every_spine_error_into_unreachable() -> None:
    engagement = Engagement(
        label="FY26",
        spine_engagement_id=ENGAGEMENT_ID,
        spine_version_id=OPEN_VERSION_ID,
        created_by="x",
    )
    refused = link_status(spine_answering(409, {"detail": "locked"}), engagement)
    assert refused.state == "unreachable"
    assert "locked" in (refused.detail or "")
    invalid = link_status(spine_answering(422, {"detail": "bad id"}), engagement)
    assert invalid.state == "unreachable"
    credential = link_status(spine_answering(401, {"detail": "no"}), engagement)
    assert credential.state == "unreachable"
    assert "credential" in (credential.detail or "")
    assert link_status(spine_answering(404, {"detail": "gone"}), engagement).state == "missing"


def test_the_detail_answers_200_with_unreachable_when_the_spine_answers_409_or_422(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = api.post(
        "/api/engagements",
        json={
            "label": "FY26",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    ).json()["id"]
    for status in (409, 422, 400):
        cast(FastAPI, api.app).state.spine_client = spine_answering(status, {"detail": "odd"})
        answer = api.get(f"/api/engagements/{engagement_id}")
        assert answer.status_code == 200, status
        assert answer.json()["spine"]["status"] == "unreachable"
        assert "odd" in answer.json()["spine"]["detail"]


# ---- D-3: the list never claims a link is verified ---------------------------------------


def test_the_list_reports_a_stored_link_as_recorded_never_verified(api: TestClient) -> None:
    use_spine(api)
    api.post("/api/engagements", json={"label": "plain"})
    api.post(
        "/api/engagements",
        json={
            "label": "linked",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    )
    listed = {entry["label"]: entry["spine"] for entry in api.get("/api/engagements").json()}
    assert listed["plain"]["status"] == "unlinked"
    assert listed["linked"]["status"] == "recorded"
    assert "open the engagement to verify" in listed["linked"]["detail"]
    assert all(entry["status"] != "verified" for entry in listed.values())
    linked_id = next(
        entry["id"] for entry in api.get("/api/engagements").json() if entry["label"] == "linked"
    )
    assert api.get(f"/api/engagements/{linked_id}").json()["spine"]["status"] == "verified"
