"""Engagements and their Spine link (architecture D8)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import Session

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.config import Settings
from oak_misstatements.models import Engagement
from oak_misstatements.schemas.engagements import EngagementIn, SpineLinkIn
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.engagements import (
    LinkStatus,
    create_engagement,
    get_engagement,
    link_status,
    list_engagements,
    misstatement_count,
    recorded_status,
    set_spine_link,
)
from oak_misstatements.services.reconciliation import reconcile
from oak_misstatements.services.spine_client import SpineClient
from oak_misstatements.services.thresholds import current_threshold

router = APIRouter(tags=["engagements"])


def engagement_json(
    session: Session,
    client: SpineClient | None,
    engagement: Engagement,
    settings: Settings,
    *,
    status: LinkStatus,
) -> dict[str, Any]:
    return {
        "authorisation": authorisation_json(settings),
        "id": str(engagement.id),
        "label": engagement.label,
        "spine": {
            "engagement_id": (
                None
                if engagement.spine_engagement_id is None
                else str(engagement.spine_engagement_id)
            ),
            "version_id": (
                None if engagement.spine_version_id is None else str(engagement.spine_version_id)
            ),
            "status": status.state,
            "is_locked": status.is_locked,
            "detail": status.detail,
        },
        "misstatements": misstatement_count(session, engagement.id),
        "current_threshold_id": (
            None if (current := current_threshold(session, engagement)) is None else str(current.id)
        ),
        "created_by": engagement.created_by,
        "created_at": engagement.created_at.isoformat(),
    }


@router.post("/engagements", status_code=201)
def create(
    body: EngagementIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    engagement = create_engagement(session, spine, body, created_by=user)
    return engagement_json(
        session, spine, engagement, settings, status=link_status(spine, engagement)
    )


@router.get("/engagements")
def index(session: SessionDep, spine: SpineDep, settings: SettingsDep) -> list[dict[str, Any]]:
    # The list does not ask the Spine about every row, so it never says "verified": a stored
    # link is "recorded", and the detail verifies it.
    return [
        engagement_json(session, spine, engagement, settings, status=recorded_status(engagement))
        for engagement in list_engagements(session)
    ]


@router.get("/engagements/{engagement_id}")
def read(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    engagement = get_engagement(session, engagement_id)
    return engagement_json(
        session, spine, engagement, settings, status=link_status(spine, engagement)
    )


@router.post("/engagements/{engagement_id}/spine-link")
def link(
    engagement_id: uuid.UUID,
    body: SpineLinkIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    _user: UserDep,
) -> dict[str, Any]:
    engagement = set_spine_link(session, spine, get_engagement(session, engagement_id), body)
    return engagement_json(
        session, spine, engagement, settings, status=link_status(spine, engagement)
    )


@router.get("/engagements/{engagement_id}/spine-reconciliation")
def reconciliation(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """Read-only (D46): the Spine's adjustments on the pinned version against the links
    recorded here. Lists orphan proposals, records whose adjustment the Spine lacks, and
    states the two modules disagree on. Repairs nothing."""
    answer = reconcile(session, spine, get_engagement(session, engagement_id))
    answer["authorisation"] = authorisation_json(settings)
    return answer
