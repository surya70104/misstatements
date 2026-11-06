"""The evaluation (spec section 10.3, sections 4.1 and 7; D38), the soft-gate
acknowledgement, a partner-only write (D39), evaluation runs (D43), the conclusion and the
answer to the strategy prompt (D45)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from oak_misstatements.api.deps import PartnerDep, SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.config import Settings
from oak_misstatements.core.gates import (
    AGGREGATE_BASIS,
    OPINION_GATE_SCOPE,
    SIGN_OFF_GATE_SCOPE,
    Determination,
    GateExposure,
    conclusion_blockers,
    opinion_gate,
    sign_off_gate,
)
from oak_misstatements.schemas import amount
from oak_misstatements.schemas.evaluation import (
    AcknowledgementIn,
    ConclusionIn,
    EvaluationRunIn,
    StrategyResponseIn,
)
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.conclusions import (
    list_conclusions,
    record_conclusion,
    require_conclusion_allowed,
)
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.evaluation import (
    Evaluation,
    acknowledge_soft_gate,
    evaluate,
    figures,
    gate_json,
    item_json,
    not_accumulated_total,
    require_sign_off_open,
    respond_to_strategy_trigger,
    run_json,
    strategy_json,
    tests_json,
)
from oak_misstatements.services.evaluation_runs import (
    get_run,
    list_runs,
    locked_engagement,
    record_run,
)
from oak_misstatements.services.prior_period import evaluation_json as prior_period_json
from oak_misstatements.services.prior_period import py_carried_json
from oak_misstatements.services.thresholds import event_json

router = APIRouter(tags=["evaluation"])

# The route tags every write of this kind must carry so that ``tests/test_contracts.py``
# can prove it took the right dependency (D40, D45):
#
# - PARTNER_ONLY: depends on ``current_partner`` (through ``PartnerDep``);
# - SIGN_OFF: a write an unmodified opinion rests on, which is the conclusion that the
#   misstatements are not material. Depends on ``sign_off_open``: every gate blocks it;
# - MATERIAL_CONCLUSION: the conclusion that the misstatements are material. Depends on
#   ``conclusion_ready``: a gate that fires is its subject, so only what leaves the
#   evaluation unknown or unfinished blocks it.
SIGN_OFF = "sign-off"
PARTNER_ONLY = "partner-only"
MATERIAL_CONCLUSION = "material-conclusion"


def locked_evaluation(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> Evaluation:
    """The evaluation, computed with the engagement row locked: what a gate decides on and
    what a row is then inserted from are the same figures (D43, D45)."""
    engagement = locked_engagement(session, engagement_id)
    return evaluate(session, spine, engagement, settings)


def sign_off_open(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> Evaluation:
    """FastAPI dependency for every write that amounts to signing off (spec line 149; D38):
    evaluates the engagement under its row lock and refuses with a 409 naming every reason
    when the gate blocks. The conclusion that the misstatements are not material declares
    it, as must any Opinion hand-off; the contract test fails any route tagged sign-off
    that lacks it."""
    evaluation = locked_evaluation(engagement_id, session, spine, settings)
    require_sign_off_open(evaluation)
    return evaluation


def conclusion_ready(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> Evaluation:
    """FastAPI dependency for the conclusion that the misstatements are material (D45):
    refuses with a 409 while the evaluation is unknown or unfinished, and not because a
    gate fires."""
    evaluation = locked_evaluation(engagement_id, session, spine, settings)
    require_conclusion_allowed(evaluation, "material")
    return evaluation


SignOffDep = Annotated[Evaluation, Depends(sign_off_open)]
ConclusionReadyDep = Annotated[Evaluation, Depends(conclusion_ready)]


def evaluation_json(evaluation: Evaluation, settings: Settings) -> dict[str, Any]:
    threshold = evaluation.threshold
    total = evaluation.aggregate
    acknowledgement = evaluation.acknowledgement
    return {
        "engagement_id": str(evaluation.engagement.id),
        "threshold": (
            None
            if threshold is None
            else {
                "id": str(threshold.id),
                "version_no": threshold.version_no,
                "om": amount(threshold.om),
                "pm": amount(threshold.pm),
                "ctt": amount(threshold.ctt),
            }
        ),
        "aggregate": {
            **figures(total),
            "complete": total.complete,
            "counted": list(total.counted),
            "projected": list(total.projected),
            "classification_only": list(total.classification_only),
            "not_accumulated": list(total.not_accumulated),
            "not_accumulated_total": not_accumulated_total(total, evaluation.threshold),
            "escalated": list(total.escalated),
            "unresolved": list(total.unresolved),
            "excluded": [{"ref": ref, "state": state} for ref, state in total.excluded],
            "basis": AGGREGATE_BASIS,
        },
        "gates": {
            "hard": gate_json(evaluation.hard),
            "soft": {
                **gate_json(evaluation.soft),
                "pm_gate": settings.pm_gate,
                "acknowledgement": {
                    "status": acknowledgement.status,
                    "detail": acknowledgement.detail,
                    "event": (
                        None if acknowledgement.event is None else event_json(acknowledgement.event)
                    ),
                },
            },
            "strategy_trigger": strategy_json(evaluation),
        },
        # SA 450 paragraph 11(b); spec section 10.3; acceptance 5: the prior-period items
        # carried forward, their current-period and cumulative effects apart, beside
        # and together with the current year's aggregate above. No gate reads it (D61).
        "prior_period": prior_period_json(evaluation.prior_period, total, threshold),
        # SA 450 paragraph 11: material individually or in aggregate, both tests shown.
        "tests": tests_json(evaluation),
        "individually_significant": {
            "blocking": [item.ref for item in evaluation.blocking],
            "unbanded": [item.ref for item in evaluation.unbanded],
        },
        # D41: items whose state here and whose adjustment in the Spine disagree.
        "state_consistency": {"inconsistent": [item.ref for item in evaluation.inconsistent]},
        "sign_off": {
            "blocked": evaluation.sign_off.blocked,
            "reasons": list(evaluation.sign_off.reasons),
            "enforced_in": (
                "api.evaluation.sign_off_open, the dependency of every write tagged "
                "sign-off: the conclusion that the misstatements are not material declares "
                "it, and tests/test_contracts.py fails a sign-off route that lacks it "
                "(D38, D40, D45)"
            ),
        },
        # D45: the latest conclusion, whether it still stands, and what each conclusion
        # would be refused for right now.
        "conclusion": conclusion_json(evaluation),
        "items": [
            item_json(item, evaluation.views[version.id])
            for item, (_m, version) in zip(evaluation.items, evaluation.pairs, strict=True)
        ],
        # D43: the latest recorded run, and whether it still describes this evaluation.
        "latest_run": latest_run_json(evaluation),
        "authorisation": authorisation_json(settings),
    }


def conclusion_json(evaluation: Evaluation) -> dict[str, Any]:
    status = evaluation.latest_conclusion
    allowed: dict[str, Any] = {}
    determinations: tuple[Determination, ...] = ("not_material", "material")
    for determination in determinations:
        blockers = conclusion_blockers(evaluation.sign_off, determination)
        allowed[determination] = {"allowed": not blockers, "reasons": list(blockers)}
    return {
        "status": "none" if status is None else status.status,
        "detail": "no conclusion has been recorded" if status is None else status.detail,
        "run": None if status is None or status.run is None else run_json(status.run),
        "allowed": allowed,
        "requires": (
            "a partner (spec section 12), named by the trusted proxy's role claim; the run "
            "reviewed, still current; a conclusion and a basis, neither empty (acceptance 10)"
        ),
    }


def latest_run_json(evaluation: Evaluation) -> dict[str, Any]:
    status = evaluation.latest_run
    if status is None:
        return {"status": "none", "detail": "no evaluation run has been recorded", "run": None}
    return {
        "status": status.status,
        "detail": status.detail,
        "run": None if status.run is None else run_json(status.run),
    }


@router.get("/engagements/{engagement_id}/evaluation")
def read(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    engagement = get_engagement(session, engagement_id)
    return evaluation_json(evaluate(session, spine, engagement, settings), settings)


@router.post(
    "/engagements/{engagement_id}/evaluation/soft-gate-acknowledgements",
    status_code=201,
    tags=[PARTNER_ONLY],
)
def acknowledge(
    engagement_id: uuid.UUID,
    body: AcknowledgementIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    partner: PartnerDep,
) -> dict[str, Any]:
    """Partner only (spec line 142). Fails closed: without a trusted role claim naming the
    acting identity a partner, this answers 403 and writes nothing (D39)."""
    engagement = get_engagement(session, engagement_id)
    event, evaluation = acknowledge_soft_gate(
        session, spine, engagement, settings, partner=partner, note=body.note
    )
    answer = evaluation_json(evaluation, settings)
    answer["acknowledgement_event"] = event_json(event)
    return answer


@router.post("/engagements/{engagement_id}/evaluation/runs", status_code=201)
def run(
    engagement_id: uuid.UUID,
    _body: EvaluationRunIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Record an evaluation run (spec section 9): the threshold version and the four
    aggregates as they stand, append-only. Refused when the evaluation cannot be computed in
    full; a gate that fires does not stop a run, which records what was found (D43)."""
    recorded = record_run(session, spine, engagement_id, settings, actor=user)
    answer = run_json(recorded)
    answer["authorisation"] = authorisation_json(settings)
    return answer


@router.get("/engagements/{engagement_id}/evaluation/runs")
def runs(
    engagement_id: uuid.UUID, session: SessionDep, settings: SettingsDep
) -> list[dict[str, Any]]:
    engagement = get_engagement(session, engagement_id)
    answers = [run_json(entry) for entry in list_runs(session, engagement)]
    for answer in answers:
        answer["authorisation"] = authorisation_json(settings)
    return answers


@router.get("/evaluation-runs/{run_id}")
def read_run(run_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
    """One run by id, exactly as recorded, however the evaluation has moved since."""
    answer = run_json(get_run(session, run_id))
    answer["authorisation"] = authorisation_json(settings)
    return answer


def _conclude(
    determination: Determination,
    body: ConclusionIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    evaluation: Evaluation,
    partner: str,
) -> dict[str, Any]:
    recorded = record_conclusion(
        session, spine, settings, evaluation, body, determination=determination, partner=partner
    )
    answer = run_json(recorded)
    answer["authorisation"] = authorisation_json(settings)
    return answer


@router.post(
    "/engagements/{engagement_id}/evaluation/conclusions/not-material",
    status_code=201,
    tags=[SIGN_OFF, PARTNER_ONLY],
)
def conclude_not_material(
    engagement_id: uuid.UUID,
    body: ConclusionIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    partner: PartnerDep,
    evaluation: SignOffDep,
) -> dict[str, Any]:
    """Conclude that the uncorrected misstatements are not material (spec section 6.4).
    Partner only. This is the conclusion an unmodified opinion rests on, so every gate
    blocks it in the write path: the hard gate, the soft gate without a current partner
    acknowledgement, and an item above PM not yet dealt with (acceptance 6, 7, 10; D45)."""
    return _conclude("not_material", body, session, spine, settings, evaluation, partner)


@router.post(
    "/engagements/{engagement_id}/evaluation/conclusions/material",
    status_code=201,
    tags=[MATERIAL_CONCLUSION, PARTNER_ONLY],
)
def conclude_material(
    engagement_id: uuid.UUID,
    body: ConclusionIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    partner: PartnerDep,
    evaluation: ConclusionReadyDep,
) -> dict[str, Any]:
    """Conclude that the uncorrected misstatements are material (spec section 6.4). Partner
    only. A gate that fires does not block this conclusion, which records exactly that;
    an unknown or unfinished evaluation does (D45)."""
    return _conclude("material", body, session, spine, settings, evaluation, partner)


@router.get("/engagements/{engagement_id}/evaluation/conclusions")
def conclusions(
    engagement_id: uuid.UUID, session: SessionDep, settings: SettingsDep
) -> list[dict[str, Any]]:
    """Every conclusion of the engagement, newest first, each with the figures and the
    threshold version it was saved with."""
    engagement = get_engagement(session, engagement_id)
    answers = [run_json(entry) for entry in list_conclusions(session, engagement)]
    for answer in answers:
        answer["authorisation"] = authorisation_json(settings)
    return answers


@router.post("/engagements/{engagement_id}/evaluation/strategy-responses", status_code=201)
def answer_strategy_prompt(
    engagement_id: uuid.UUID,
    body: StrategyResponseIn,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Record the answer to the strategy prompt (spec section 7; SA 450 paragraph 6): whether
    the audit strategy and plan were revised, "recorded either way". Any authenticated
    identity; the spec reserves it to no one. Refused when the trigger does not fire."""
    engagement = locked_engagement(session, engagement_id)
    event, evaluation = respond_to_strategy_trigger(
        session,
        spine,
        engagement,
        settings,
        actor=user,
        strategy_revised=body.strategy_revised,
        note=body.note,
    )
    answer = evaluation_json(evaluation, settings)
    answer["strategy_response_event"] = event_json(event)
    return answer


# ---- gate exposure for other modules (architecture D18, D46) -------------------------------


def _exposure_json(
    name: str, scope: str, exposure: GateExposure, evaluation: Evaluation, settings: Settings
) -> dict[str, Any]:
    threshold = evaluation.threshold
    conclusion = evaluation.latest_conclusion
    concluded = None if conclusion is None else conclusion.run
    return {
        "gate": name,
        "status": exposure.status,
        "blocked_by": list(exposure.blocked_by),
        "undetermined_because": list(exposure.undetermined_because),
        "scope": scope,
        "engagement_id": str(evaluation.engagement.id),
        "threshold": (
            None
            if threshold is None
            else {
                "id": str(threshold.id),
                "version_no": threshold.version_no,
                "om": amount(threshold.om),
                "pm": amount(threshold.pm),
            }
        ),
        # The figures the status rests on (D18): every measure, with and without projected.
        "figures": figures(evaluation.aggregate),
        "complete": evaluation.aggregate.complete,
        # What those figures leave out as clearly trivial (spec section 4; D53), so that a
        # module reading the gate can see it and need not infer it.
        "not_accumulated": list(evaluation.aggregate.not_accumulated),
        # The prior-period items carried forward, as labels and aggregates. The gate
        # status above does not rest on them (D61): a module reading the gate sees
        # them here and need not infer that.
        "prior_period": py_carried_json(evaluation.prior_period, evaluation.aggregate, threshold),
        "hard_gate": gate_json(evaluation.hard),
        "soft_gate": {
            **gate_json(evaluation.soft),
            "pm_gate": settings.pm_gate,
            "acknowledgement": evaluation.acknowledgement.status,
        },
        "conclusion": {
            "status": "none" if conclusion is None else conclusion.status,
            "determination": None if concluded is None else concluded.determination,
            "run_no": None if concluded is None else concluded.run_no,
        },
        "read_only": True,
        "authorisation": authorisation_json(settings),
    }


@router.get("/engagements/{engagement_id}/gates/opinion")
def read_opinion_gate(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """The opinion gate (spec section 7; D18): open, blocked or undetermined, with the
    figures. Read-only, for the module that issues the opinion. ``blocked`` means an
    unmodified opinion cannot be issued on the uncorrected misstatements as they stand."""
    evaluation = evaluate(session, spine, get_engagement(session, engagement_id), settings)
    exposure = opinion_gate(
        evaluation.hard,
        evaluation.soft,
        pm_gate=settings.pm_gate,
        unbanded=evaluation.unbanded,
        inconsistent=evaluation.inconsistent,
    )
    return _exposure_json("opinion", OPINION_GATE_SCOPE, exposure, evaluation, settings)


@router.get("/engagements/{engagement_id}/gates/sign-off")
def read_sign_off_gate(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """The sign-off block (spec section 7, acceptance 6; D18): open, blocked or
    undetermined, with the figures. Read-only. The same decision the conclusion that the
    misstatements are not material is refused on."""
    evaluation = evaluate(session, spine, get_engagement(session, engagement_id), settings)
    exposure = sign_off_gate(
        evaluation.sign_off,
        evaluation.hard,
        evaluation.soft,
        unbanded=evaluation.unbanded,
        inconsistent=evaluation.inconsistent,
    )
    return _exposure_json("sign-off", SIGN_OFF_GATE_SCOPE, exposure, evaluation, settings)
