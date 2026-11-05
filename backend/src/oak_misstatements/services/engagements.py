"""Engagements and their link to a Financial Spine engagement and version (architecture D8).

The link may be set while no misstatement exists. Once one does, changing the pinned
version is the re-pointing question of pending decision B10 and is refused with its name.
Nothing from the Spine is copied here: the ids are stored, the figures are read when needed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oak_misstatements.errors import (
    Conflict,
    Invalid,
    ModuleError,
    NotFound,
    PendingDecision,
)
from oak_misstatements.models import Engagement, Misstatement
from oak_misstatements.schemas.engagements import EngagementIn, SpineLinkIn
from oak_misstatements.services.spine_client import SpineClient

# recorded: a link is stored but this answer did not ask the Spine about it (the list).
LinkState = Literal[
    "unlinked", "not_configured", "recorded", "verified", "missing", "unreachable", "mismatch"
]


@dataclass(frozen=True)
class LinkStatus:
    state: LinkState
    is_locked: bool | None
    detail: str | None


def require_spine(client: SpineClient | None) -> SpineClient:
    if client is None:
        raise Conflict(
            "no Financial Spine is configured (OAK_SPINE_URL), so nothing can be checked "
            "against or proposed to one"
        )
    return client


def verify_link(
    client: SpineClient, engagement_id: uuid.UUID, version_id: uuid.UUID | None
) -> None:
    """The Spine engagement must exist and the version, when given, must belong to it."""
    client.engagement(engagement_id)  # NotFound carries the Spine's answer
    if version_id is not None:
        version = client.version(version_id)
        if version.engagement_id != engagement_id:
            raise Invalid(
                f"Spine version {version_id} belongs to engagement {version.engagement_id}, "
                f"not {engagement_id}"
            )


def create_engagement(
    session: Session, client: SpineClient | None, body: EngagementIn, *, created_by: str
) -> Engagement:
    if body.spine_engagement_id is not None:
        verify_link(require_spine(client), body.spine_engagement_id, body.spine_version_id)
    engagement = Engagement(
        label=body.label,
        spine_engagement_id=body.spine_engagement_id,
        spine_version_id=body.spine_version_id,
        created_by=created_by,
    )
    session.add(engagement)
    session.flush()
    return engagement


def misstatement_count(session: Session, engagement_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Misstatement)
            .where(Misstatement.engagement_id == engagement_id)
        )
        or 0
    )


def set_spine_link(
    session: Session, client: SpineClient | None, engagement: Engagement, body: SpineLinkIn
) -> Engagement:
    """Set, change or clear the link. Clearing the engagement clears the version."""
    changes_version = body.spine_version_id != engagement.spine_version_id
    if changes_version and misstatement_count(session, engagement.id):
        raise PendingDecision(
            "B10",
            "this engagement already has misstatements proposed on its pinned Spine version; "
            "whether it may be re-pointed to another version, and how the records follow, "
            "is not decided",
        )
    if body.spine_engagement_id is not None:
        verify_link(require_spine(client), body.spine_engagement_id, body.spine_version_id)
    engagement.spine_engagement_id = body.spine_engagement_id
    engagement.spine_version_id = body.spine_version_id
    session.flush()
    return engagement


def recorded_status(engagement: Engagement) -> LinkStatus:
    """What is stored, without asking the Spine: for the list, which never verifies."""
    if engagement.spine_engagement_id is None:
        return LinkStatus("unlinked", None, "no Financial Spine engagement is linked")
    return LinkStatus(
        "recorded", None, "a Spine link is recorded; open the engagement to verify it"
    )


def link_status(client: SpineClient | None, engagement: Engagement) -> LinkStatus:
    if engagement.spine_engagement_id is None:
        return LinkStatus("unlinked", None, "no Financial Spine engagement is linked")
    if client is None:
        return LinkStatus(
            "not_configured", None, "a Spine link is recorded but OAK_SPINE_URL is unset"
        )
    try:
        client.engagement(engagement.spine_engagement_id)
        if engagement.spine_version_id is None:
            return LinkStatus("verified", None, "engagement verified; no version pinned")
        version = client.version(engagement.spine_version_id)
    except NotFound as missing:
        return LinkStatus("missing", None, str(missing))
    except ModuleError as failed:
        # Unreachable, refused, or an answer that makes no sense for a read: a status on
        # this engagement, never a 409 or 422 leaking out of a GET.
        return LinkStatus("unreachable", None, str(failed))
    if version.engagement_id != engagement.spine_engagement_id:
        return LinkStatus(
            "mismatch", version.is_locked, "the pinned version belongs to another engagement"
        )
    return LinkStatus("verified", version.is_locked, None)


def get_engagement(session: Session, engagement_id: uuid.UUID) -> Engagement:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise NotFound(f"no engagement {engagement_id}")
    return engagement


def list_engagements(session: Session) -> list[Engagement]:
    return list(session.scalars(select(Engagement).order_by(Engagement.created_at, Engagement.id)))
