"""Evaluation runs (spec section 9 ``evaluation``; section 2, paragraphs 10, 11 and 15;
acceptance 4; architecture D43): record the evaluation as it stands, append-only.

A run is recorded only when the evaluation can be computed in full: thresholds exist, every
uncorrected misstatement's effects are resolved, and no misstatement's state disagrees with
the Financial Spine. Otherwise the four aggregates the row carries would be known to be
short or wrong, and nothing is written. A gate that fires does **not** stop a run: the run
is the record of what the evaluation found, material or not. Concluding on it is Stage 5.

Materiality is reassessed before the evaluation (SA 450 paragraph 10): the request must say
so, and the run and an event both record that it did. If materiality needs revising, a new
threshold version is set first; every band then recomputes, and the run is made against it.

The engagement row is locked before the evaluation is computed, so the figures a run stores
are the figures of one consistent moment: no move and no new misstatement can slip in
between the computation and the insert.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oak_misstatements.config import Settings
from oak_misstatements.core.gates import AGGREGATE_BASIS
from oak_misstatements.errors import Conflict, ModuleError, NotFound
from oak_misstatements.models import Engagement, Event
from oak_misstatements.models.evaluation import EvaluationRun
from oak_misstatements.schemas import amount
from oak_misstatements.services.evaluation import (
    Evaluation,
    evaluate,
    figures,
    item_labels,
    not_accumulated_total,
    tests_json,
)
from oak_misstatements.services.prior_period import py_carried_json
from oak_misstatements.services.spine_client import SpineClient

MATERIALITY_REASSESSED = "materiality_reassessed"
EVALUATION_CONCLUDED = "evaluation_concluded"


@dataclass(frozen=True)
class ConclusionFields:
    """What a concluded row adds to a run (D45)."""

    determination: str
    conclusion: str
    basis: str
    reviewed_run_id: uuid.UUID
    reviewed_run_no: int


class NotEvaluable(Conflict):
    """The evaluation cannot be computed in full, so no run is recorded."""


def require_evaluable(evaluation: Evaluation) -> None:
    reasons: list[str] = []
    if evaluation.threshold is None:
        reasons.append(
            "no thresholds have been set, and a run records the threshold version it was "
            "made against (spec section 9)"
        )
    if not evaluation.aggregate.complete:
        reasons.append(
            "the effects of "
            + ", ".join(evaluation.aggregate.unresolved)
            + " cannot be determined, so the aggregate would be short"
        )
    if evaluation.inconsistent:
        reasons.append(
            ", ".join(item.ref for item in evaluation.inconsistent)
            + " disagree with the Financial Spine about their state, so the aggregate would "
            "count an item the Spine has posted or leave one out"
        )
    if reasons:
        raise NotEvaluable(
            "no evaluation run was recorded: " + "; ".join(reasons) + " (architecture D43)"
        )


def _spine_lock(client: SpineClient | None, engagement: Engagement) -> bool | None:
    """Whether the pinned Spine version is locked, when that can be read (pending B10)."""
    if client is None or engagement.spine_version_id is None:
        return None
    try:
        return client.version(engagement.spine_version_id).is_locked
    except ModuleError:
        return None


def run_detail(
    evaluation: Evaluation, settings: Settings, *, spine_locked: bool | None
) -> dict[str, Any]:
    """Labels and aggregates only: never a Dr, a Cr or one misstatement's effect."""
    threshold = evaluation.threshold
    assert threshold is not None  # noqa: S101 - require_evaluable has run
    total = evaluation.aggregate
    return {
        "threshold": {
            "id": str(threshold.id),
            "version_no": threshold.version_no,
            "om": amount(threshold.om),
            "pm": amount(threshold.pm),
            "ctt": amount(threshold.ctt),
        },
        "figures": figures(total),
        "basis": AGGREGATE_BASIS,
        "items": item_labels(evaluation),
        "counted": list(total.counted),
        "projected": list(total.projected),
        "classification_only": list(total.classification_only),
        "not_accumulated": list(total.not_accumulated),
        "not_accumulated_total": not_accumulated_total(total, threshold),
        "escalated": list(total.escalated),
        "excluded": [{"ref": ref, "state": state} for ref, state in total.excluded],
        "tests": tests_json(evaluation),
        "gates": {
            "hard": {
                "status": evaluation.hard.status,
                "fires_on": list(evaluation.hard.fires_on),
                "depends_on_projected": evaluation.hard.depends_on_projected,
            },
            "soft": {
                "status": evaluation.soft.status,
                "fires_on": list(evaluation.soft.fires_on),
                "depends_on_projected": evaluation.soft.depends_on_projected,
                "pm_gate": settings.pm_gate,
                "acknowledgement": evaluation.acknowledgement.status,
            },
        },
        "sign_off": {
            "blocked": evaluation.sign_off.blocked,
            "reasons": list(evaluation.sign_off.reasons),
        },
        "spine": {
            "version_id": (
                None
                if evaluation.engagement.spine_version_id is None
                else str(evaluation.engagement.spine_version_id)
            ),
            "locked": spine_locked,
        },
        "identity_mode": settings.auth,
        "strategy_trigger": {
            "status": "not_configured"
            if evaluation.strategy is None
            else evaluation.strategy.status,
            "response": (
                None
                if evaluation.strategy_response is None
                else evaluation.strategy_response.status
            ),
        },
    }


def locked_engagement(session: Session, engagement_id: uuid.UUID) -> Engagement:
    """The engagement, its row locked for the rest of the transaction: the evaluation
    computed next and the row inserted from it belong to one moment."""
    engagement = session.execute(
        select(Engagement)
        .where(Engagement.id == engagement_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if engagement is None:
        raise NotFound(f"no engagement {engagement_id}")
    return engagement


def insert_run(
    session: Session,
    client: SpineClient | None,
    evaluation: Evaluation,
    settings: Settings,
    *,
    actor: str,
    conclusion: ConclusionFields | None = None,
) -> EvaluationRun:
    """Insert one ``evaluation`` row from an evaluation computed under the engagement lock.
    With ``conclusion`` the row carries the conclusion and its figures together (D45);
    without, it is a run that concludes nothing (D43)."""
    require_evaluable(evaluation)
    engagement = evaluation.engagement
    threshold = evaluation.threshold
    assert threshold is not None  # noqa: S101 - require_evaluable has run
    total = evaluation.aggregate
    highest = session.scalar(
        select(func.max(EvaluationRun.run_no)).where(EvaluationRun.engagement_id == engagement.id)
    )
    detail = run_detail(evaluation, settings, spine_locked=_spine_lock(client, engagement))
    if conclusion is not None:
        detail["reviewed_run"] = {
            "id": str(conclusion.reviewed_run_id),
            "run_no": conclusion.reviewed_run_no,
        }
    run = EvaluationRun(
        id=uuid.uuid4(),
        engagement_id=engagement.id,
        run_no=int(highest or 0) + 1,
        threshold_id=threshold.id,
        agg_gross_pbt=total.profit.gross,
        agg_net_pbt=total.profit.net,
        agg_gross_na=total.net_assets.gross,
        agg_net_na=total.net_assets.net,
        materiality_reassessed=True,
        py_carried=py_carried_json(evaluation.prior_period, total, threshold),
        detail=detail,
        evaluated_by=actor,
        determination=None if conclusion is None else conclusion.determination,
        conclusion=None if conclusion is None else conclusion.conclusion,
        basis=None if conclusion is None else conclusion.basis,
        concluded_by=None if conclusion is None else actor,
    )
    session.add(run)
    session.flush()
    # The reassessment is an event of the engagement's trail too (D13).
    session.add(
        Event(
            engagement_id=engagement.id,
            kind=MATERIALITY_REASSESSED,
            actor=actor,
            payload={
                "evaluation_run_id": str(run.id),
                "run_no": run.run_no,
                "threshold_id": str(threshold.id),
                "threshold_version_no": threshold.version_no,
                "basis": "SA 450 paragraph 10: materiality reassessed before the evaluation",
            },
        )
    )
    if conclusion is not None:
        session.add(
            Event(
                engagement_id=engagement.id,
                kind=EVALUATION_CONCLUDED,
                actor=actor,
                payload={
                    "evaluation_run_id": str(run.id),
                    "run_no": run.run_no,
                    "determination": conclusion.determination,
                    "reviewed_run_id": str(conclusion.reviewed_run_id),
                    "reviewed_run_no": conclusion.reviewed_run_no,
                    "threshold_id": str(threshold.id),
                    "threshold_version_no": threshold.version_no,
                },
            )
        )
    session.flush()
    return run


def record_run(
    session: Session,
    client: SpineClient | None,
    engagement_id: uuid.UUID,
    settings: Settings,
    *,
    actor: str,
) -> EvaluationRun:
    engagement = locked_engagement(session, engagement_id)
    evaluation = evaluate(session, client, engagement, settings)
    return insert_run(session, client, evaluation, settings, actor=actor)


def list_runs(session: Session, engagement: Engagement) -> list[EvaluationRun]:
    """Every run, newest first, by run number."""
    return list(
        session.scalars(
            select(EvaluationRun)
            .where(EvaluationRun.engagement_id == engagement.id)
            .order_by(EvaluationRun.run_no.desc())
        )
    )


def get_run(session: Session, run_id: uuid.UUID) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise NotFound(f"no evaluation run {run_id}")
    return run
