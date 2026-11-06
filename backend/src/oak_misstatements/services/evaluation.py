"""The evaluation: the aggregate, the gates and the sign-off decision for one engagement
(spec sections 4.1, 7, 10.3; architecture D38), and the soft-gate acknowledgement (D39).

Nothing here is stored except the acknowledgement, an append-only event, and the
evaluation runs of ``services/evaluation_runs.py``, which record this evaluation as it stood
when each was made (D43). The aggregate and
the gates are computed on every read from the Spine's live lines, each misstatement's
recorded classification (D32) and the current threshold version (D33), exactly as the
schedule computes each band, so the two can never disagree.

An acknowledgement names the threshold version and the figures it acknowledged. It stands
while both are unchanged; a later threshold version or a changed aggregate makes it stale,
and the gate asks again. That is this module's reading of "a required partner
acknowledgement" (spec line 142), recorded as an assumption in D39.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from oak_misstatements.config import Settings
from oak_misstatements.core import gates
from oak_misstatements.core.banding import band_item
from oak_misstatements.core.states import expected_spine_status
from oak_misstatements.errors import Conflict
from oak_misstatements.models import Engagement, Event, Misstatement, MisstatementVersion, Threshold
from oak_misstatements.models.evaluation import EvaluationRun
from oak_misstatements.schemas import amount
from oak_misstatements.services.misstatements import (
    SpineView,
    current_versions,
    measure,
    spine_views,
)
from oak_misstatements.services.spine_client import SpineClient
from oak_misstatements.services.thresholds import current_threshold, lines_of

SOFT_GATE_ACKNOWLEDGED = "soft_gate_acknowledged"
STRATEGY_TRIGGER_RESPONSE = "strategy_trigger_response"


@dataclass(frozen=True)
class Acknowledgement:
    status: str  # not_required | required | acknowledged | stale | unavailable
    event: Event | None
    detail: str


@dataclass(frozen=True)
class RunStatus:
    """The latest recorded evaluation run against the evaluation as it stands now (D43)."""

    status: str  # none | current | stale
    detail: str
    run: EvaluationRun | None


@dataclass(frozen=True)
class Evaluation:
    engagement: Engagement
    threshold: Threshold | None
    items: list[gates.Item]
    views: dict[uuid.UUID, SpineView]
    pairs: list[tuple[Misstatement, MisstatementVersion]]
    aggregate: gates.Aggregate
    hard: gates.GateResult
    soft: gates.GateResult
    acknowledgement: Acknowledgement
    blocking: tuple[gates.Item, ...]
    unbanded: tuple[gates.Item, ...]
    sign_off: gates.SignOff
    inconsistent: tuple[gates.Item, ...] = ()
    latest_run: RunStatus | None = None
    latest_conclusion: RunStatus | None = None
    strategy: gates.StrategyTrigger | None = None
    strategy_response: Acknowledgement | None = None


def _item(
    misstatement: Misstatement,
    version: MisstatementVersion,
    view: SpineView,
    threshold: Threshold | None,
) -> gates.Item:
    effects = view.effects
    band = None
    if effects is not None and threshold is not None:
        result = band_item(
            effects,
            lines_of(threshold),
            threshold_id=threshold.id,
            threshold_version_no=threshold.version_no,
            range_low=version.range_low,
            range_high=version.range_high,
        )
        band = None if result is None else result.band
    return gates.Item(
        misstatement_id=misstatement.id,
        ref=misstatement.ref,
        type=version.type,
        state=version.state,
        profit=None if effects is None else effects.profit_before_tax,
        net_assets=None if effects is None else effects.net_assets,
        classification_only=effects is not None and effects.classification_only,
        band=band,
        refusal_reason=version.refusal_reason,
        spine_adjustment_status=None if view.adjustment is None else view.adjustment.status,
    )


def figures(total: gates.Aggregate) -> dict[str, Any]:
    """The figures an acknowledgement is tied to: every measure, both ways, with and
    without the projected items."""

    def measure_json(entry: gates.Measure) -> dict[str, str]:
        return {
            "gross": amount(entry.gross),
            "net": amount(entry.net),
            "gross_without_projected": amount(entry.gross_without_projected),
            "net_without_projected": amount(entry.net_without_projected),
            "projected_gross": amount(entry.projected_gross),
            "factual_gross": amount(entry.factual_gross),
            "judgemental_gross": amount(entry.judgemental_gross),
        }

    return {
        "profit_before_tax": measure_json(total.profit),
        "net_assets": measure_json(total.net_assets),
    }


NOT_ACCUMULATED_BASIS = (
    "the gross size, on each measure, of the items that band clearly trivial one by one; "
    "while it is below the clearly-trivial threshold on both measures those items are left "
    "out of the aggregate; once it reaches the threshold on either, all of them are "
    "accumulated, because SA 450 paragraph A2 describes clearly trivial matters as clearly "
    "inconsequential 'whether taken individually or in aggregate' and treats any uncertainty "
    "as not clearly trivial (architecture D57); measuring 'in aggregate' gross against the "
    "threshold itself is the conservative reading, for the CA to confirm (register S14, "
    "question 2)"
)


def not_accumulated_total(total: gates.Aggregate, threshold: Threshold | None) -> dict[str, Any]:
    """What the items that are clearly trivial one by one come to together, and whether
    that brought them into the aggregate (D57)."""
    ctt = None if threshold is None else threshold.ctt
    highest = max(total.left_out_profit, total.left_out_net_assets)
    return {
        "profit_before_tax_gross": amount(total.left_out_profit),
        "net_assets_gross": amount(total.left_out_net_assets),
        "ctt": None if ctt is None else amount(ctt),
        "at_or_above_ctt": ctt is not None and highest >= ctt,
        "accumulated_together": list(total.accumulated_together),
        "basis": NOT_ACCUMULATED_BASIS,
    }


def acknowledgements(session: Session, engagement: Engagement) -> list[Event]:
    return list(
        session.scalars(
            select(Event)
            .where(Event.engagement_id == engagement.id, Event.kind == SOFT_GATE_ACKNOWLEDGED)
            .order_by(Event.seq.desc())
        )
    )


def acknowledgement_status(
    session: Session,
    engagement: Engagement,
    threshold: Threshold | None,
    total: gates.Aggregate,
    soft: gates.GateResult,
) -> Acknowledgement:
    if soft.status != "fires":
        return Acknowledgement(
            "not_required", None, "the soft gate does not fire on the current figures"
        )
    latest = next(iter(acknowledgements(session, engagement)), None)
    if latest is None:
        return Acknowledgement("required", None, "no partner acknowledgement is recorded")
    if threshold is None or latest.payload.get("threshold_id") != str(threshold.id):
        return Acknowledgement(
            "stale",
            latest,
            "the last acknowledgement was given against another threshold version",
        )
    if latest.payload.get("figures") != figures(total):
        return Acknowledgement(
            "stale", latest, "the aggregate has changed since the last acknowledgement"
        )
    return Acknowledgement("acknowledged", latest, "acknowledged on these figures")


def evaluate(
    session: Session, client: SpineClient | None, engagement: Engagement, settings: Settings
) -> Evaluation:
    pairs = current_versions(session, engagement)
    views = spine_views(session, client, engagement, [version for _m, version in pairs])
    threshold = current_threshold(session, engagement)
    items = [_item(m, v, views[v.id], threshold) for m, v in pairs]
    total = gates.aggregate(items, None if threshold is None else threshold.ctt)
    om, pm = gates.lines_or_none(None if threshold is None else lines_of(threshold))
    hard = gates.gate("hard", total, om)
    soft = gates.gate("soft", total, pm)
    acknowledgement = acknowledgement_status(session, engagement, threshold, total, soft)
    blocking = gates.blocking_items(items)
    unbanded = gates.unbanded_items(items)
    inconsistent = gates.inconsistent_items(items)
    decision = gates.sign_off(
        hard,
        soft,
        pm_gate=settings.pm_gate,
        soft_acknowledged=acknowledgement.status == "acknowledged",
        blocking=blocking,
        unbanded=unbanded,
        inconsistent=inconsistent,
    )
    evaluation = Evaluation(
        engagement,
        threshold,
        items,
        views,
        pairs,
        total,
        hard,
        soft,
        acknowledgement,
        blocking,
        unbanded,
        decision,
        inconsistent=inconsistent,
    )
    strategy = gates.strategy_trigger(total, om, settings.strategy_trigger_fraction)
    return replace(
        evaluation,
        latest_run=run_status(session, evaluation),
        latest_conclusion=conclusion_status(session, evaluation),
        strategy=strategy,
        strategy_response=strategy_response_status(session, engagement, threshold, total, strategy),
    )


def strategy_response_status(
    session: Session,
    engagement: Engagement,
    threshold: Threshold | None,
    total: gates.Aggregate,
    strategy: gates.StrategyTrigger,
) -> Acknowledgement:
    """Whether the prompt to revisit the strategy has been answered on these figures
    (spec section 7: "recorded either way")."""
    if strategy.status != "fires":
        return Acknowledgement("not_required", None, "the strategy trigger does not fire")
    latest = session.scalar(
        select(Event)
        .where(Event.engagement_id == engagement.id, Event.kind == STRATEGY_TRIGGER_RESPONSE)
        .order_by(Event.seq.desc())
        .limit(1)
    )
    if latest is None:
        return Acknowledgement("required", None, "the strategy prompt has not been answered")
    if threshold is None or latest.payload.get("threshold_id") != str(threshold.id):
        return Acknowledgement(
            "stale", latest, "the last answer was given against another threshold version"
        )
    if latest.payload.get("figures") != figures(total):
        return Acknowledgement("stale", latest, "the aggregate has changed since the last answer")
    return Acknowledgement("recorded", latest, "answered on these figures")


def item_labels(evaluation: Evaluation) -> list[dict[str, Any]]:
    """Every misstatement the evaluation saw, as labels: its reference, the version it was
    read at, its state, type and band. Never an amount."""
    return [
        {
            "ref": item.ref,
            "version_no": version.version_no,
            "state": item.state,
            "type": item.type,
            "band": None if item.band is None else item.band.value,
            "classification_only": item.classification_only,
            "uncorrected": item.uncorrected,
        }
        for item, (_m, version) in zip(evaluation.items, evaluation.pairs, strict=True)
    ]


def tests_json(evaluation: Evaluation) -> dict[str, Any]:
    """SA 450 paragraph 11: material individually or in aggregate, both tests, both shown."""
    om = None if evaluation.threshold is None else evaluation.threshold.om
    return {
        "individual": {
            "individually_significant": [
                item.ref for item in gates.individually_significant_items(evaluation.items)
            ],
            "at_or_above_om": [item.ref for item in gates.items_at_or_above(evaluation.items, om)],
            "basis": gates.INDIVIDUAL_BASIS,
        },
        "aggregate": {
            "status": evaluation.hard.status,
            "om": None if om is None else amount(om),
            "fires_on": list(evaluation.hard.fires_on),
            "highest_measure": (
                None if evaluation.hard.highest is None else amount(evaluation.hard.highest)
            ),
            "depends_on_projected": evaluation.hard.depends_on_projected,
            "basis": gates.GATE_BASIS,
        },
    }


def latest_run(session: Session, engagement: Engagement) -> EvaluationRun | None:
    return session.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.engagement_id == engagement.id)
        .order_by(EvaluationRun.run_no.desc())
        .limit(1)
    )


def run_difference(run: EvaluationRun, evaluation: Evaluation) -> str | None:
    """Why ``run`` no longer describes the evaluation, or None when it still does. A run is
    a record of one moment; it is never updated, so anything that has changed since makes
    it stale."""
    threshold = evaluation.threshold
    if threshold is None or run.threshold_id != threshold.id:
        return "the thresholds have been revised since it was recorded"
    if run.detail.get("items") != item_labels(evaluation):
        return "a misstatement has been raised, moved or re-banded since it was recorded"
    if run.detail.get("figures") != figures(evaluation.aggregate):
        return "the aggregate has changed since it was recorded"
    return None


def run_status(session: Session, evaluation: Evaluation) -> RunStatus:
    """Whether the latest recorded run still describes the evaluation."""
    run = latest_run(session, evaluation.engagement)
    if run is None:
        return RunStatus("none", "no evaluation run has been recorded", None)
    difference = run_difference(run, evaluation)
    if difference is None:
        return RunStatus("current", "the latest run describes the evaluation as it stands", run)
    wording = {
        "the thresholds have been revised since it was recorded": (
            "the thresholds have been revised since the latest run was recorded"
        ),
        "a misstatement has been raised, moved or re-banded since it was recorded": (
            "a misstatement has been raised, moved or re-banded since the latest run was recorded"
        ),
        "the aggregate has changed since it was recorded": (
            "the aggregate has changed since the latest run was recorded"
        ),
    }
    return RunStatus("stale", wording[difference], run)


def conclusion_status(session: Session, evaluation: Evaluation) -> RunStatus:
    """The latest conclusion, and whether it still stands on the evaluation as it is now
    (D45). A conclusion is never edited: when the figures, the thresholds or a misstatement
    change, it is stale and a new one is needed."""
    run = session.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.engagement_id == evaluation.engagement.id,
            EvaluationRun.determination.is_not(None),
        )
        .order_by(EvaluationRun.run_no.desc())
        .limit(1)
    )
    if run is None:
        return RunStatus("none", "no conclusion has been recorded", None)
    difference = run_difference(run, evaluation)
    if difference is None:
        return RunStatus("current", "the latest conclusion stands on the evaluation as it is", run)
    return RunStatus("stale", f"the latest conclusion is out of date: {difference}", run)


def run_json(run: EvaluationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "engagement_id": str(run.engagement_id),
        "run_no": run.run_no,
        "threshold_id": str(run.threshold_id),
        "threshold_version_no": run.detail.get("threshold", {}).get("version_no"),
        "agg_gross_pbt": amount(run.agg_gross_pbt),
        "agg_net_pbt": amount(run.agg_net_pbt),
        "agg_gross_na": amount(run.agg_gross_na),
        "agg_net_na": amount(run.agg_net_na),
        "materiality_reassessed": run.materiality_reassessed,
        "evaluated_by": run.evaluated_by,
        "at": run.at.isoformat(),
        # The conclusion, on the row that carries its figures; null on a run that concludes
        # nothing (D45).
        "concluded": run.determination is not None,
        "determination": run.determination,
        "conclusion": run.conclusion,
        "basis": run.basis,
        "concluded_by": run.concluded_by,
        "detail": run.detail,
    }


def strategy_json(evaluation: Evaluation) -> dict[str, Any]:
    strategy = evaluation.strategy
    response = evaluation.strategy_response
    if strategy is None or response is None:
        return {"status": "not_configured", "detail": NOT_CONFIGURED, "response": None}
    return {
        "status": strategy.status,
        "fraction": None if strategy.fraction is None else f"{strategy.fraction.normalize():f}",
        "line": None if strategy.line is None else amount(strategy.line),
        "fires_on": list(strategy.fires_on),
        "highest_measure": None if strategy.highest is None else amount(strategy.highest),
        "detail": NOT_CONFIGURED if strategy.status == "not_configured" else STRATEGY_BASIS,
        "blocks": False,  # a prompt, never a block (spec section 7)
        "response": {"status": response.status, "detail": response.detail},
    }


NOT_CONFIGURED = (
    "the 'approaching materiality' band is not set (OAK_STRATEGY_TRIGGER_FRACTION), so the "
    "strategy trigger is not evaluated; what the band should be is pending decision B5"
)
STRATEGY_BASIS = (
    "fires when any measure is at or above the declared fraction of overall materiality "
    "(spec section 7; SA 450 paragraph 6); a prompt to revisit the audit strategy and plan, "
    "recorded either way; it blocks nothing (architecture D45)"
)


def respond_to_strategy_trigger(
    session: Session,
    client: SpineClient | None,
    engagement: Engagement,
    settings: Settings,
    *,
    actor: str,
    strategy_revised: bool,
    note: str | None,
) -> tuple[Event, Evaluation]:
    """Record the answer to the strategy prompt on the current figures."""
    evaluation = evaluate(session, client, engagement, settings)
    strategy = evaluation.strategy
    response = evaluation.strategy_response
    assert strategy is not None and response is not None  # noqa: S101 - evaluate sets both
    if strategy.status != "fires":
        raise Conflict(
            f"the strategy trigger does not fire ({strategy.status}); there is nothing to answer"
        )
    if response.status == "recorded":
        raise Conflict("the strategy prompt is already answered on these figures")
    assert evaluation.threshold is not None and strategy.line is not None  # noqa: S101
    event = Event(
        engagement_id=engagement.id,
        kind=STRATEGY_TRIGGER_RESPONSE,
        actor=actor,
        payload={
            "threshold_id": str(evaluation.threshold.id),
            "threshold_version_no": evaluation.threshold.version_no,
            "fraction": f"{strategy.fraction.normalize():f}" if strategy.fraction else None,
            "line": amount(strategy.line),
            "fires_on": list(strategy.fires_on),
            "figures": figures(evaluation.aggregate),
            "strategy_revised": strategy_revised,
            "note": note,
            "identity_mode": settings.auth,
        },
    )
    session.add(event)
    session.flush()
    return event, evaluate(session, client, engagement, settings)


class GateBlocked(Conflict):
    """A write that amounts to signing off was refused by the gate (spec line 149)."""


def require_sign_off_open(evaluation: Evaluation) -> None:
    """The write-path check (spec section 7, acceptance 6 and 7): every write that amounts to
    signing off, the conclusion when Stage 4 builds it and the Opinion module's call, must
    pass through here. Fails closed."""
    if evaluation.sign_off.blocked:
        raise GateBlocked(
            "sign-off is blocked: " + "; ".join(evaluation.sign_off.reasons) + " (architecture D38)"
        )


def acknowledge_soft_gate(
    session: Session,
    client: SpineClient | None,
    engagement: Engagement,
    settings: Settings,
    *,
    partner: str,
    note: str | None,
) -> tuple[Event, Evaluation]:
    """Record the partner's acknowledgement of the soft gate on the current figures. The
    caller has already established that ``partner`` holds the partner role (D39)."""
    evaluation = evaluate(session, client, engagement, settings)
    if evaluation.soft.status != "fires":
        raise Conflict(
            f"the soft gate does not fire ({evaluation.soft.status}); there is nothing to "
            "acknowledge"
        )
    if evaluation.acknowledgement.status == "acknowledged":
        raise Conflict("these figures are already acknowledged on this threshold version")
    assert evaluation.threshold is not None  # noqa: S101 - the gate fired, so a version exists
    event = Event(
        engagement_id=engagement.id,
        kind=SOFT_GATE_ACKNOWLEDGED,
        actor=partner,
        payload={
            "threshold_id": str(evaluation.threshold.id),
            "threshold_version_no": evaluation.threshold.version_no,
            "pm": amount(evaluation.threshold.pm),
            "pm_gate": settings.pm_gate,
            "fires_on": list(evaluation.soft.fires_on),
            "depends_on_projected": evaluation.soft.depends_on_projected,
            "figures": figures(evaluation.aggregate),
            "note": note,
            "identity_mode": settings.auth,
        },
    )
    session.add(event)
    session.flush()
    return event, evaluate(session, client, engagement, settings)


def _optional_amount(value: Decimal | None) -> str | None:
    return None if value is None else amount(value)


def gate_json(result: gates.GateResult) -> dict[str, Any]:
    return {
        "line": _optional_amount(result.line),
        "status": result.status,
        "fires_on": list(result.fires_on),
        "fires_without_projected": result.fires_without_projected,
        "depends_on_projected": result.depends_on_projected,
        "highest_measure": _optional_amount(result.highest),
        "blocks": result.blocks,
        "basis": result.basis,
    }


def item_json(item: gates.Item, view: SpineView) -> dict[str, Any]:
    return {
        "id": str(item.misstatement_id),
        "ref": item.ref,
        "type": item.type,
        "projected": item.projected,
        "state": item.state,
        "uncorrected": item.uncorrected,
        "profit_before_tax": _optional_amount(item.profit),
        "net_assets": _optional_amount(item.net_assets),
        "classification_only": item.classification_only,
        "measure": _optional_amount(measure(view)),
        "band": None if item.band is None else item.band.value,
        "spine_status": view.state,
        "spine_adjustment_status": None if view.adjustment is None else view.adjustment.status,
        "expected_spine_adjustment_status": expected_spine_status(item.state),
    }
