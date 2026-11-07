"""Moving a misstatement through its states (spec section 3.3; acceptance 3 and 11; D41).

Every move inserts the next ``misstatement_version``: the previous row is never touched,
so the versions are the state trail. The new version copies every field that does not
change, records the new state with its date and reason, and receives its own copy of the
classification snapshot (labels only, D32), so its effects are read exactly as before.

The order is chosen so that a failure leaves nothing half-done:

1. the engagement row is locked and the latest version read, so two moves cannot race;
2. the move is checked against the state machine;
3. for a final state the Spine's adjustment is **read** and must be ``proposed`` (or already
   decided the way this move needs, which is how a move interrupted after the Spine's answer
   is completed); any other status is refused before anything is written;
4. the new version and its snapshot are written and flushed, so a database rule that
   refuses them does so **before** the Spine is asked for anything;
5. only then is the Spine's decision sent. If the Spine refuses or cannot be reached the
   request fails and the transaction rolls back: nothing was written in either place.

The one window that remains is a commit that fails after the Spine has decided. The Spine
then holds a decision this module has not recorded; reading the misstatement reports the
disagreement (``state_consistency``), the evaluation blocks on it, and repeating the same
move completes it without a second decision (step 3).

No amount is read, copied or stored by any of this.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from oak_misstatements.core.states import (
    FINAL,
    SPINE_DECISION,
    check_transition,
    decision_note,
)
from oak_misstatements.errors import Conflict, ServiceUnavailable
from oak_misstatements.models import (
    Engagement,
    Misstatement,
    MisstatementLineClass,
    MisstatementVersion,
)
from oak_misstatements.schemas.transitions import TransitionIn
from oak_misstatements.services.engagements import require_spine
from oak_misstatements.services.misstatements import get_misstatement, snapshot_for
from oak_misstatements.services.spine_client import SpineAdjustment, SpineClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpineOutcome:
    """What the move asked of the Spine and what the Spine holds afterwards."""

    decision: str | None  # accepted | refused | None when the move asks nothing
    decided_now: bool  # False when the Spine had already decided it this way
    adjustment: SpineAdjustment | None
    note: str | None


def copy_snapshot(
    session: Session, source_version_id: uuid.UUID, target_version_id: uuid.UUID
) -> None:
    """The new version's own copy of the classification snapshot. Labels only."""
    for row in snapshot_for(session, source_version_id):
        session.add(
            MisstatementLineClass(
                misstatement_version_id=target_version_id,
                position=row.position,
                ledger_key=row.ledger_key,
                ledger_name=row.ledger_name,
                parent_chain=list(row.parent_chain),
                head_id=row.head_id,
                nature=row.nature,
                head_item=row.head_item,
                section=row.section,
                spine_version_id=row.spine_version_id,
                tree_version=row.tree_version,
            )
        )


def _readable_adjustment(
    spine: SpineClient, engagement: Engagement, current: MisstatementVersion, to: str, ref: str
) -> SpineAdjustment:
    """The Spine's adjustment, which must be open or already decided the way ``to`` needs."""
    if engagement.spine_version_id is None:
        raise Conflict(
            "no Financial Spine version is pinned to this engagement, so the adjustment "
            "cannot be decided"
        )
    adjustment = spine.adjustment(engagement.spine_version_id, current.spine_adjustment_id)
    wanted = SPINE_DECISION[to]
    if adjustment.status not in ("proposed", wanted):
        raise Conflict(
            f"{ref} cannot become {to}: the Financial Spine already decided its adjustment "
            f"{adjustment.status} ({adjustment.decided_by or 'unknown'}, "
            f"{adjustment.decision_note or 'no note'}), and the Spine decides once. Nothing "
            "was written. A person must reconcile the two modules (architecture D41)"
        )
    return adjustment


def transition(
    session: Session,
    client: SpineClient | None,
    misstatement_id: uuid.UUID,
    body: TransitionIn,
    *,
    actor: str,
) -> tuple[Misstatement, list[MisstatementVersion], SpineOutcome]:
    misstatement, _versions = get_misstatement(session, misstatement_id)
    engagement = session.execute(
        select(Engagement)
        .where(Engagement.id == misstatement.engagement_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    _misstatement, versions = get_misstatement(session, misstatement_id)  # under the lock
    current = versions[-1]
    # Read now: after a refused flush the session expires every loaded row, and reading the
    # reference then would raise a second error that hides the first (D42).
    ref = misstatement.ref
    check_transition(current.state, body.to)

    adjustment: SpineAdjustment | None = None
    spine: SpineClient | None = None
    if body.to in FINAL:
        spine = require_spine(client)
        adjustment = _readable_adjustment(spine, engagement, current, body.to, ref)

    now = dt.datetime.now(dt.UTC)
    record = MisstatementVersion(
        misstatement_id=misstatement.id,
        version_no=current.version_no + 1,
        type=current.type,
        description=current.description,
        raised_by=current.raised_by,
        raised_from=current.raised_from,
        source_ref=current.source_ref,
        origin=current.origin,
        state=body.to,
        communicated_at=now if body.to == "communicated" else current.communicated_at,
        decided_at=now if body.to in FINAL else None,
        refusal_reason=body.reason if body.to == "refused" else None,
        withdrawal_reason=body.reason if body.to == "withdrawn" else None,
        spine_adjustment_id=current.spine_adjustment_id,
        spine_kind=current.spine_kind,
        range_low=current.range_low,
        range_high=current.range_high,
        sample_ref=current.sample_ref,
        projection_basis=current.projection_basis,
        sampling_method=current.sampling_method,
        population_value=current.population_value,
        population_size=current.population_size,
        sample_value=current.sample_value,
        sample_size=current.sample_size,
        known_error_in_sample=current.known_error_in_sample,
        created_by=actor,
    )
    try:
        session.add(record)
        session.flush()
        copy_snapshot(session, current.id, record.id)
        session.flush()
    except SQLAlchemyError as error:
        cause: BaseException = getattr(error, "orig", None) or error
        logger.error("%s: %s refused by the database: %s", ref, body.to, cause)
        raise ServiceUnavailable(
            f"{ref} could not be recorded as {body.to}: {type(cause).__name__}: "
            f"{cause}. Nothing was sent to the Financial Spine and nothing was written"
        ) from error

    if spine is None or adjustment is None:
        return misstatement, [*versions, record], SpineOutcome(None, False, None, None)

    wanted = SPINE_DECISION[body.to]
    if adjustment.status == wanted:
        # The Spine already holds this decision (a move interrupted after the Spine's answer,
        # or a decision taken there directly): record the state, decide nothing twice.
        logger.warning(
            "%s recorded as %s: the Spine had already decided adjustment %s %s",
            ref,
            body.to,
            adjustment.adjustment_id,
            adjustment.status,
        )
        return (
            misstatement,
            [*versions, record],
            SpineOutcome(wanted, False, adjustment, adjustment.decision_note),
        )
    note = decision_note(body.to, ref, actor, body.reason)
    assert engagement.spine_version_id is not None  # noqa: S101 - checked when it was read
    decided = spine.decide(
        engagement.spine_version_id, current.spine_adjustment_id, status=wanted, note=note
    )
    if decided.status != wanted:
        raise ServiceUnavailable(
            f"the Financial Spine answered {decided.status!r} to a decision of {wanted!r} on "
            f"{ref}; nothing was written here"
        )
    return misstatement, [*versions, record], SpineOutcome(wanted, True, decided, note)
