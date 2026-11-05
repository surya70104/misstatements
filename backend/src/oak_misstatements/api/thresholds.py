"""Thresholds (spec section 4): set a version, read the current one with its Spine PM
check, read the history, read one version by its id, read the engagement's event trail."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.schemas.thresholds import ThresholdIn
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.thresholds import (
    current_threshold,
    event_json,
    events,
    get_threshold,
    history,
    pm_check,
    set_threshold,
    threshold_json,
)

router = APIRouter(tags=["thresholds"])


@router.post("/engagements/{engagement_id}/thresholds", status_code=201)
def create(
    engagement_id: uuid.UUID,
    body: ThresholdIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    engagement = get_engagement(session, engagement_id)
    threshold, event = set_threshold(session, spine, engagement, body, set_by=user)
    answer = threshold_json(threshold, check=pm_check(spine, engagement, threshold))
    answer["authorisation"] = authorisation_json(settings)
    answer["recompute_event"] = None if event is None else event_json(event)
    return answer


@router.get("/engagements/{engagement_id}/thresholds")
def current(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    engagement = get_engagement(session, engagement_id)
    threshold = current_threshold(session, engagement)
    if threshold is None:
        return {"current": None, "detail": "no thresholds have been set for this engagement"}
    answer = threshold_json(threshold, check=pm_check(spine, engagement, threshold))
    answer["authorisation"] = authorisation_json(settings)
    return {"current": answer}


@router.get("/engagements/{engagement_id}/thresholds/history")
def versions(
    engagement_id: uuid.UUID, session: SessionDep, settings: SettingsDep
) -> list[dict[str, Any]]:
    engagement = get_engagement(session, engagement_id)
    answers = [threshold_json(threshold) for threshold in history(session, engagement)]
    for answer in answers:
        answer["authorisation"] = authorisation_json(settings)
    return answers


@router.get("/engagements/{engagement_id}/events")
def trail(engagement_id: uuid.UUID, session: SessionDep) -> list[dict[str, Any]]:
    engagement = get_engagement(session, engagement_id)
    return [event_json(event) for event in events(session, engagement)]


@router.get("/thresholds/{threshold_id}")
def read_version(
    threshold_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """One threshold version, current or superseded, with the Spine PM cross-check against
    the version it was set against (D35): the ids in a banding block or a recompute event
    resolve here."""
    threshold = get_threshold(session, threshold_id)
    engagement = get_engagement(session, threshold.engagement_id)
    answer = threshold_json(threshold, check=pm_check(spine, engagement, threshold))
    answer["authorisation"] = authorisation_json(settings)
    return answer
