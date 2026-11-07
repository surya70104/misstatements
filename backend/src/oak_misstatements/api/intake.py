"""The intake hooks (spec section 8; acceptance 1; architecture D64): one endpoint per
source, each taking what that source attaches and nothing else, and each raising the
misstatement exactly as the general endpoint does: balanced Dr/Cr lines proposed to the
Financial Spine, the record written in the ``raised`` state, the origin kept with it.

- ``POST .../intake/wp``: an area tester, with the working paper reference;
- ``POST .../intake/run``: an accepted WorkMind agent run, with its run id and at least one
  source-row citation;
- ``POST .../intake/note``: a review note, with its reference and a link if it has one;
- ``POST .../intake/manual``: a manual entry, which requires a working paper reference.

Sampling arrives through any of them as a projected misstatement naming its sample and
projection basis (spec section 3.2). Any authenticated identity may raise, as for the
general endpoint; who may raise from which source is the firm's (register B9b)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import Session

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.api.misstatements import misstatement_json
from oak_misstatements.config import Settings
from oak_misstatements.schemas.intake import (
    ManualIntakeIn,
    NoteIntakeIn,
    RunIntakeIn,
    WorkingPaperIntakeIn,
)
from oak_misstatements.schemas.misstatements import MisstatementIn
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.misstatements import raise_misstatement
from oak_misstatements.services.spine_client import SpineClient
from oak_misstatements.services.thresholds import current_threshold

router = APIRouter(tags=["intake"])


def _raise(
    session: Session,
    spine: SpineClient | None,
    settings: Settings,
    engagement_id: uuid.UUID,
    body: MisstatementIn,
    user: str,
) -> dict[str, Any]:
    engagement = get_engagement(session, engagement_id)
    misstatement, version, view = raise_misstatement(
        session, spine, engagement, body, raised_by=user
    )
    threshold = current_threshold(session, engagement)
    return misstatement_json(misstatement, version, view, threshold, settings, versions=[version])


@router.post("/engagements/{engagement_id}/intake/wp", status_code=201)
def from_working_paper(
    engagement_id: uuid.UUID,
    body: WorkingPaperIntakeIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """An area tester raises a misstatement with its working paper reference attached."""
    return _raise(session, spine, settings, engagement_id, body.to_misstatement(), user)


@router.post("/engagements/{engagement_id}/intake/run", status_code=201)
def from_agent_run(
    engagement_id: uuid.UUID,
    body: RunIntakeIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """An accepted WorkMind agent run's exception becomes a misstatement, carrying the run
    id and the source-row citations. Whether the run was accepted is WorkMind's to say:
    this module records what it is told and by whom."""
    return _raise(session, spine, settings, engagement_id, body.to_misstatement(), user)


@router.post("/engagements/{engagement_id}/intake/note", status_code=201)
def from_review_note(
    engagement_id: uuid.UUID,
    body: NoteIntakeIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """A reviewer converts a review note into a misstatement."""
    return _raise(session, spine, settings, engagement_id, body.to_misstatement(), user)


@router.post("/engagements/{engagement_id}/intake/manual", status_code=201)
def manual(
    engagement_id: uuid.UUID,
    body: ManualIntakeIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """A manual entry: allowed, and it requires a working paper reference."""
    return _raise(session, spine, settings, engagement_id, body.to_misstatement(), user)
