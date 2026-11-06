"""Rolling a misstatement forward from another engagement (SA 450 paragraph 11(b);
architecture D61).

A prior-period item may cite a misstatement of another engagement of this module. The
backend then reads that misstatement itself: it must be uncorrected there (raised,
communicated or refused: the aggregate's own reading, F3), and its effects must be known.
Its description and its two effects there are copied onto the carried item; they are never
taken from the request.

What is **not** copied, because it cannot be: the item's effect on the current period and
its cumulative effect. Those remain a person's, entered with their basis (register B6).

Whether the other engagement is in fact the prior period's is not something this module
can know: an engagement here carries no period. The person rolling forward names the period.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from oak_misstatements.config import Settings
from oak_misstatements.errors import Conflict, Invalid, NotFound
from oak_misstatements.models import Engagement, Misstatement
from oak_misstatements.schemas import amount
from oak_misstatements.services.evaluation import Evaluation, evaluate
from oak_misstatements.services.prior_period import Source, latest, versions
from oak_misstatements.services.spine_client import SpineClient

CANDIDATES_BASIS = (
    "the misstatements of the other engagement that are uncorrected there (raised, "
    "communicated or refused) and whose effects are known; each can be rolled forward once, "
    "with its effects there copied by the backend; its current-period and cumulative "
    "effects here are entered by a person (register B6; architecture D61)"
)


def _label(source: Engagement, ref: str) -> str:
    return f"{source.label}, {ref}"


def source_for(
    session: Session,
    client: SpineClient | None,
    settings: Settings,
    engagement: Engagement,
    misstatement_id: uuid.UUID,
) -> Source:
    """The misstatement an item is rolled forward from, read from the backend's own record
    and checked. Raises when it cannot be carried forward."""
    misstatement = session.get(Misstatement, misstatement_id)
    if misstatement is None:
        raise NotFound(f"no misstatement {misstatement_id} to roll forward")
    if misstatement.engagement_id == engagement.id:
        raise Invalid(
            f"{misstatement.ref} is a misstatement of this engagement: it is the current "
            "year's, and already in its aggregate; only a misstatement of another "
            "engagement is rolled forward"
        )
    other = session.get(Engagement, misstatement.engagement_id)
    assert other is not None  # noqa: S101 - the foreign key guarantees it
    evaluation = evaluate(session, client, other, settings)
    item = next(entry for entry in evaluation.items if entry.misstatement_id == misstatement.id)
    version = next(v for m, v in evaluation.pairs if m.id == misstatement.id)
    if not item.uncorrected:
        raise Conflict(
            f"{_label(other, item.ref)} is {item.state} there; only an uncorrected "
            "misstatement is carried forward (SA 450 paragraph 11(b))"
        )
    if item.profit is None or item.net_assets is None:
        raise Conflict(
            f"the effects of {_label(other, item.ref)} cannot be determined there (the "
            "Financial Spine could not be read, or a line is not classified), so it cannot "
            "be rolled forward; nothing was saved"
        )
    return Source(
        misstatement_id=misstatement.id,
        description=version.description,
        source_ref=_label(other, item.ref),
        profit=item.profit,
        net_assets=item.net_assets,
    )


def candidates_json(
    session: Session, engagement: Engagement, other: Engagement, evaluation: Evaluation
) -> dict[str, Any]:
    """What could be rolled forward from ``other``, whose evaluation is ``evaluation``."""
    carried_as = {
        row.source_misstatement_id: row.ref
        for row in latest(versions(session, engagement))
        if row.carried and row.source_misstatement_id is not None
    }
    available: list[dict[str, Any]] = []
    not_available: list[dict[str, Any]] = []
    for item, (_misstatement, version) in zip(evaluation.items, evaluation.pairs, strict=True):
        if not item.uncorrected:
            continue
        if item.profit is None or item.net_assets is None:
            not_available.append(
                {"ref": item.ref, "reason": "its effects cannot be determined there"}
            )
            continue
        available.append(
            {
                "misstatement_id": str(item.misstatement_id),
                "ref": item.ref,
                "description": version.description,
                "type": item.type,
                "state": item.state,
                "profit_before_tax": amount(item.profit),
                "net_assets": amount(item.net_assets),
                # The reference it is already carried under here, when it is.
                "carried_as": carried_as.get(item.misstatement_id),
            }
        )
    return {
        "engagement_id": str(engagement.id),
        "from_engagement": {"id": str(other.id), "label": other.label},
        "candidates": available,
        "not_available": not_available,
        "basis": CANDIDATES_BASIS,
    }
