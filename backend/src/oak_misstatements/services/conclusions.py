"""The conclusion (spec sections 6.4, 7, 9 and 12; acceptance 6, 7 and 10; D45).

A conclusion is a new row of ``evaluation``: the figures, the threshold version and the
conclusion are inserted together, under the engagement lock, so the conclusion carries the
figures it was based on and nothing can move between the evaluation and the insert. No
earlier row is ever updated; a revised conclusion is another row.

Three things are enforced here, in the write path, whatever a screen shows:

1. **Who.** The route is partner-only (spec section 12: the words are the partner's) and
   fails closed without a trusted role claim (D39, D40). ``concluded_by`` is that identity.
2. **The gates.** What blocks depends on what is being concluded:

   - *not material* is the conclusion an unmodified opinion rests on, so it needs sign-off
     to be open: every reason of ``core.gates.sign_off`` blocks it, the hard gate, the soft
     gate without a current partner acknowledgement, a PM gate the firm set to hard, an
     item above PM not yet corrected, refused with a reason or withdrawn, and anything
     that leaves the evaluation unknown;
   - *material* is the record that the misstatements are material. The hard gate blocks
     an unmodified opinion (spec section 7), not the documenting of this conclusion, so a
     gate that fires does not block it. What still blocks it is anything that leaves the
     evaluation unknown or unfinished: no thresholds, an unresolved or unbanded item, a
     state the Spine disputes, and an item above PM still raised or communicated
     (acceptance 6).

3. **What was reviewed.** The request names the evaluation run the partner reviewed. If
   that run no longer describes the evaluation, nothing is saved: the figures on the new
   row are then exactly the figures that were reviewed (acceptance 10).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from oak_misstatements.config import Settings
from oak_misstatements.core import gates
from oak_misstatements.errors import Conflict, NotFound
from oak_misstatements.models import Engagement
from oak_misstatements.models.evaluation import EvaluationRun
from oak_misstatements.schemas.evaluation import ConclusionIn
from oak_misstatements.services.evaluation import Evaluation, GateBlocked, run_difference
from oak_misstatements.services.evaluation_runs import ConclusionFields, insert_run
from oak_misstatements.services.spine_client import SpineClient

SAID = {"not_material": "are not material", "material": "are material"}


def require_conclusion_allowed(evaluation: Evaluation, determination: gates.Determination) -> None:
    """The gate, for this determination. Fails closed."""
    blockers = gates.conclusion_blockers(evaluation.sign_off, determination)
    if blockers:
        raise GateBlocked(
            f"a conclusion that the uncorrected misstatements {SAID[determination]} cannot "
            "be saved: " + "; ".join(blockers) + " (architecture D45)"
        )


def reviewed_run(session: Session, evaluation: Evaluation, run_id: uuid.UUID) -> EvaluationRun:
    """The run the partner says they reviewed, which must be this engagement's and must
    still describe the evaluation."""
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise NotFound(f"no evaluation run {run_id}")
    if run.engagement_id != evaluation.engagement.id:
        raise Conflict(f"evaluation run {run_id} belongs to another engagement; nothing was saved")
    difference = run_difference(run, evaluation)
    if difference is not None:
        raise Conflict(
            f"run {run.run_no}, the one reviewed, no longer describes the evaluation: "
            f"{difference}. Nothing was saved. Record a new run, review it, and conclude on "
            "that (architecture D45)"
        )
    return run


def record_conclusion(
    session: Session,
    client: SpineClient | None,
    settings: Settings,
    evaluation: Evaluation,
    body: ConclusionIn,
    *,
    determination: gates.Determination,
    partner: str,
) -> EvaluationRun:
    """Insert the concluded row. ``evaluation`` was computed under the engagement lock by
    the route's dependency, which has already applied the gate; it is applied again here so
    that no caller of this function can skip it."""
    require_conclusion_allowed(evaluation, determination)
    reviewed = reviewed_run(session, evaluation, body.reviewed_run_id)
    return insert_run(
        session,
        client,
        evaluation,
        settings,
        actor=partner,
        conclusion=ConclusionFields(
            determination=determination,
            conclusion=body.conclusion,
            basis=body.basis,
            reviewed_run_id=reviewed.id,
            reviewed_run_no=reviewed.run_no,
        ),
    )


def list_conclusions(session: Session, engagement: Engagement) -> list[EvaluationRun]:
    """Every concluded row, newest first."""
    return list(
        session.scalars(
            select(EvaluationRun)
            .where(
                EvaluationRun.engagement_id == engagement.id,
                EvaluationRun.determination.is_not(None),
            )
            .order_by(EvaluationRun.run_no.desc())
        )
    )
