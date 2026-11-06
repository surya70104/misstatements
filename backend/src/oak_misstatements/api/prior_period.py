"""Prior-period uncorrected misstatements carried forward (SA 450 paragraph 11(b); spec
section 4.1; acceptance 5; architecture D61): read the schedule of carried items, record
one by hand or roll one forward from another engagement, revise its figures, or stop
carrying it. Every write appends a version; none changes or removes an earlier one.

The current-period and cumulative effects of an item are entered by a person with their
basis. The evaluation shows their totals apart from the current year's own misstatements,
and the two together on each basis (``api/evaluation.py``). No gate reads them."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.errors import Invalid
from oak_misstatements.schemas.prior_period import (
    PriorPeriodIn,
    PriorPeriodRemovalIn,
    PriorPeriodRevisionIn,
)
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.evaluation import evaluate
from oak_misstatements.services.evaluation_runs import locked_engagement
from oak_misstatements.services.prior_period import (
    item_json,
    listing_json,
    record,
    remove,
    revise,
    versions,
)
from oak_misstatements.services.prior_period_source import candidates_json, source_for

router = APIRouter(tags=["prior-period"])


@router.get("/engagements/{engagement_id}/prior-period")
def read(engagement_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
    """The schedule of prior-period items: each carried item with its current-period and
    its cumulative effect, the removed ones, every version, and the totals on each basis."""
    engagement = get_engagement(session, engagement_id)
    return {
        **listing_json(engagement, versions(session, engagement)),
        "authorisation": authorisation_json(settings),
    }


@router.get("/engagements/{engagement_id}/prior-period/candidates")
def candidates(
    engagement_id: uuid.UUID,
    from_engagement_id: uuid.UUID,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """What could be rolled forward from another engagement: its uncorrected misstatements
    with their effects there. Read-only."""
    engagement = get_engagement(session, engagement_id)
    if from_engagement_id == engagement.id:
        raise Invalid(
            "an engagement's own misstatements are the current year's; name another "
            "engagement to roll forward from"
        )
    other = get_engagement(session, from_engagement_id)
    return {
        **candidates_json(session, engagement, other, evaluate(session, spine, other, settings)),
        "authorisation": authorisation_json(settings),
    }


@router.post("/engagements/{engagement_id}/prior-period", status_code=201)
def create(
    engagement_id: uuid.UUID,
    body: PriorPeriodIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Record a prior-period uncorrected misstatement with its current-period and
    cumulative effects: entered by hand, or rolled forward from a misstatement of another
    engagement, whose effects there the backend copies. Who may do so is the firm's to
    decide (register B9b): any authenticated identity, as for the module's other writes."""
    engagement = locked_engagement(session, engagement_id)
    source = (
        None
        if body.source_misstatement_id is None
        else source_for(session, spine, settings, engagement, body.source_misstatement_id)
    )
    item = record(session, engagement, body, actor=user, source=source)
    return {
        **listing_json(engagement, versions(session, engagement)),
        "recorded": item_json(item),
        "authorisation": authorisation_json(settings),
    }


@router.post("/engagements/{engagement_id}/prior-period/{ref}/revisions", status_code=201)
def revision(
    engagement_id: uuid.UUID,
    ref: str,
    body: PriorPeriodRevisionIn,
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Revise a carried item's four effects and their basis. A new version; the earlier
    one is kept."""
    engagement = locked_engagement(session, engagement_id)
    item = revise(session, engagement, ref, body, actor=user)
    return {
        **listing_json(engagement, versions(session, engagement)),
        "recorded": item_json(item),
        "authorisation": authorisation_json(settings),
    }


@router.post("/engagements/{engagement_id}/prior-period/{ref}/removal", status_code=201)
def removal(
    engagement_id: uuid.UUID,
    ref: str,
    body: PriorPeriodRemovalIn,
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Stop carrying an item forward, with the reason. A new version; the item and its
    figures stay in the history."""
    engagement = locked_engagement(session, engagement_id)
    item = remove(session, engagement, ref, reason=body.reason, actor=user)
    return {
        **listing_json(engagement, versions(session, engagement)),
        "recorded": item_json(item),
        "authorisation": authorisation_json(settings),
    }
